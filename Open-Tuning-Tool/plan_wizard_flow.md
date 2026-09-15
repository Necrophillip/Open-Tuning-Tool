# Ponytail Review

`advisor.py:L59`: shrink: 16 spaces of indent. `sub_recommendations = []`.

`wizard_shell.py:L36-42`: yagni: static `WIZARD_STEPS` out of sync with `page_classes`. Define `FLOWS` dict mapping mission -> `[ (PageClass, Title, Subtitle), ... ]`.

`wizard_shell.py:L116-143`: delete: pre-instantiating every page class regardless of mission. Re-instantiate the stack once when the mission is selected.

`log_page.py:L55`: shrink: `def _on_mission_changed(idx): modes = ["FILTERS", "PIDS", "COMPLEMENTARY"]; self.state.tuning_mode = modes[idx]; self.mission_selected.emit(modes[idx])`.

net: -10 lines possible.

## [Goal Description]
Fix the `IndentationError` in `advisor.py` and implement a truly dynamic Wizard flow based on the selected tuning mission. Currently, the UI stepper `WIZARD_STEPS` is hardcoded to 5 steps, but there are 6 page classes, causing index out-of-bounds crashes and sending the user to the wrong pages.

## User Review Required
No review required. This is a correctness and alignment fix to match the UI to the logical flows.

## Proposed Changes

### Core
#### [MODIFY] fpv_tuner/core/pid_tuning/advisor.py
- Fix line 59 indentation.

### UI
#### [MODIFY] fpv_tuner/ui/wizard_shell.py
- Delete static `WIZARD_STEPS`.
- Define `FLOW_FILTERS`, `FLOW_PIDS`, `FLOW_COMPLEMENTARY` as lists of `(PageClass, dict)` tuples.
- Subscribe to `log_page.mission_selected`. When it fires, call a new `_rebuild_stack(mode)` method that clears `self.stack`, clears `self._pages`, instantiates only the pages for that mode, and resets the `StepIndicator`.

#### [MODIFY] fpv_tuner/ui/pages/log_page.py
- Expose `mission_selected = pyqtSignal(str)` and emit it in `_on_mission_changed`.

## Verification Plan
### Automated Tests
- Syntax check `advisor.py`.
- Run all tests.
### Manual Verification
- Launch app, click "Fase 1", check sidebar (should be Log -> Analysis -> Diagnosis -> Export -> Iterate).
- Click "Fase 2", check sidebar (should be Log -> Analysis -> Tuning -> Export -> Iterate).
