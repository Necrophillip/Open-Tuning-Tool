"""
AI Tuning Advisor — optional LLM-powered tuning assistant.

Pure Python, no Qt.  Takes engine outputs (findings, prescription,
session history) and asks an LLM to explain, contextualize, and
suggest.  Falls back gracefully if no API key is configured.

Designed to be plugged into any LLM provider (Kimi, OpenAI, etc.).
Currently implements a generic HTTP call pattern.
"""
import os
import json
import urllib.request
import urllib.error
from dataclasses import dataclass, field
from typing import Optional

from fpv_tuner.core.diagnostics import Finding, Severity
from fpv_tuner.core.prescription import Prescription
from fpv_tuner.core.session_history import SessionSnapshot


# ── Configuration ────────────────────────────────────────────────

DEFAULT_MODEL = "kimi-k2-0711-preview"
DEFAULT_BASE_URL = "https://api.moonshot.cn/v1"


@dataclass
class AiConfig:
    """Configuration for the AI advisor."""
    api_key: str = ""
    model: str = DEFAULT_MODEL
    base_url: str = DEFAULT_BASE_URL
    enabled: bool = False

    @classmethod
    def from_env(cls) -> "AiConfig":
        """Load from environment variables."""
        key = os.environ.get("KIMI_API_KEY", "")
        return cls(
            api_key=key,
            model=os.environ.get("KIMI_MODEL", DEFAULT_MODEL),
            base_url=os.environ.get("KIMI_BASE_URL", DEFAULT_BASE_URL),
            enabled=bool(key),
        )

    @classmethod
    def from_file(cls, path: str = "") -> "AiConfig":
        """Load from a JSON config file."""
        if not path:
            path = os.path.expanduser("~/.fpv_tuner/ai_config.json")
        if not os.path.exists(path):
            return cls.from_env()
        with open(path) as fh:
            data = json.load(fh)
        return cls(
            api_key=data.get("api_key", ""),
            model=data.get("model", DEFAULT_MODEL),
            base_url=data.get("base_url", DEFAULT_BASE_URL),
            enabled=data.get("enabled", True) and bool(data.get("api_key", "")),
        )


# ── Context builder ──────────────────────────────────────────────

def _build_context(
    findings: list[Finding],
    prescription: Optional[Prescription],
    sessions: list[SessionSnapshot],
) -> str:
    """Build a text context for the LLM from engine outputs."""
    parts = []

    # Findings
    if findings:
        parts.append("## Current Findings")
        for f in findings:
            parts.append(f"- [{f.severity.value.upper()}] {f.title}")
            parts.append(f"  Explanation: {f.explanation}")
            if f.recommendation:
                parts.append(f"  Recommendation: {f.recommendation}")
    else:
        parts.append("## Current Findings\nNo issues detected.")

    # Prescription
    if prescription and prescription.changes:
        parts.append("\n## Proposed CLI Changes")
        for c in prescription.changes:
            parts.append(f"- set {c.setting} = {c.new_value}  (was {c.old_value})")
            parts.append(f"  Reason: {c.reason}")
        if prescription.notes:
            parts.append(f"\nNotes: {prescription.notes[0]}")
    else:
        parts.append("\n## Proposed CLI Changes\nNo changes recommended.")

    # Session history
    if len(sessions) > 1:
        parts.append(f"\n## Session History ({len(sessions)} sessions)")
        for s in sessions[:5]:
            parts.append(
                f"- {s.session_id[:8]}: gyro_rms={s.gyro_rms}, "
                f"issues={s.n_critical}c/{s.n_warning}w, changes={s.n_changes}"
            )

    return "\n".join(parts)


SYSTEM_PROMPT = """You are an expert FPV drone tuner specializing in Betaflight 4.5.
You analyze blackbox log data and provide clear, actionable tuning advice.

Rules:
- Be concise and specific. No generic advice.
- Explain the "why" behind each recommendation.
- Correlate multiple findings when relevant (e.g., "noise at 200Hz + frame resonance suggests a bent prop or loose motor").
- Compare with previous sessions when available.
- Use plain English. Avoid jargon unless necessary.
- Format: short paragraphs, bullet points for actions.
- If data is insufficient, say so."""


# ── Public API ────────────────────────────────────────────────────

@dataclass
class AiAdvice:
    """Response from the AI advisor."""
    success: bool = False
    text: str = ""
    model: str = ""
    error: str = ""
    tokens_used: int = 0


def get_ai_advice(
    findings: list[Finding],
    prescription: Optional[Prescription] = None,
    sessions: list[SessionSnapshot] = None,
    config: Optional[AiConfig] = None,
    question: str = "",
) -> AiAdvice:
    """
    Get AI-powered tuning advice.

    Falls back to a rule-based summary if no API key is configured.
    """
    if config is None:
        config = AiConfig.from_file()

    if sessions is None:
        sessions = []

    # Fallback: no API key → generate rule-based summary
    if not config.enabled:
        return _fallback_advice(findings, prescription)

    context = _build_context(findings, prescription, sessions)

    user_msg = f"""Analyze this FPV drone tuning data and provide advice.

{context}

{f"Specific question: {question}" if question else "Provide overall tuning assessment and next steps."}
"""

    try:
        return _call_llm(config, SYSTEM_PROMPT, user_msg)
    except Exception as e:
        return AiAdvice(success=False, error=str(e))


def _fallback_advice(
    findings: list[Finding],
    prescription: Optional[Prescription],
) -> AiAdvice:
    """Rule-based advice when no LLM is available."""
    n_crit = sum(1 for f in findings if f.severity == Severity.CRITICAL)
    n_warn = sum(1 for f in findings if f.severity == Severity.WARNING)
    n_changes = len(prescription.changes) if prescription else 0

    if n_crit == 0 and n_warn == 0:
        text = "✅ Your quad looks healthy! No critical issues detected. Fly and enjoy."
    else:
        text = f"Found {n_crit} critical and {n_warn} warning issues.\n"
        if n_changes:
            text += f"Recommended: apply {n_changes} CLI changes.\n"
        text += "Review the findings above for details."

    return AiAdvice(success=True, text=text, model="rule-based")


def _call_llm(config: AiConfig, system: str, user: str) -> AiAdvice:
    """Make an HTTP call to the LLM API."""
    url = f"{config.base_url}/chat/completions"
    payload = json.dumps({
        "model": config.model,
        "messages": [
            {"role": "system", "content": system},
            {"role": "user", "content": user},
        ],
        "temperature": 0.3,
        "max_tokens": 1000,
    }).encode()

    req = urllib.request.Request(
        url,
        data=payload,
        headers={
            "Content-Type": "application/json",
            "Authorization": f"Bearer {config.api_key}",
        },
    )

    with urllib.request.urlopen(req, timeout=30) as resp:
        data = json.loads(resp.read().decode())

    choice = data["choices"][0]
    usage = data.get("usage", {})

    return AiAdvice(
        success=True,
        text=choice["message"]["content"],
        model=data.get("model", config.model),
        tokens_used=usage.get("total_tokens", 0),
    )
