"""
Utilities for merging multiple Blackbox log segments into a single continuous DataFrame.

When a BBL/BFL file is fragmented (contains multiple flight sessions), blackbox_decode
produces one CSV per session. This module merges those CSVs back into one DataFrame,
handling:
  - Column alignment across segments (segments may have different column sets).
  - Time discontinuities (offsets each segment so time is monotonically increasing).
  - Loop-iteration column realignment.
"""

import os
import pandas as pd
import numpy as np


def merge_segments(csv_paths):
    """
    Merge multiple decoded Blackbox CSV segments into a single DataFrame.

    Args:
        csv_paths (list[str]): Ordered list of paths to decoded CSV files.

    Returns:
        pandas.DataFrame: A merged DataFrame with continuous time, or None on failure.
    """
    if not csv_paths:
        return None

    if len(csv_paths) == 1:
        return _load_single(csv_paths[0])

    # Sort segments by the numeric index embedded in their filenames
    # (e.g., "LOG00001.01.csv", "LOG00001.02.csv", ...)
    csv_paths = _sort_segments(csv_paths)

    dataframes = []
    for path in csv_paths:
        df = _load_single(path)
        if df is not None and not df.empty:
            dataframes.append(df)
            print(f"  [merge] Loaded segment '{os.path.basename(path)}': {len(df)} rows, "
                  f"{len(df.columns)} columns")

    if not dataframes:
        print("  [merge] No valid segments found.")
        return None

    if len(dataframes) == 1:
        return dataframes[0]

    # --- Align columns: use the union of all columns, filling NaN for missing ---
    all_columns = _get_ordered_union_columns(dataframes)
    aligned = [df.reindex(columns=all_columns) for df in dataframes]

    # --- Merge with time offset ---
    merged = _concat_with_time_offset(aligned)

    print(f"  [merge] Merged {len(dataframes)} segments -> {len(merged)} total rows")
    return merged


def merge_segments_from_dir(directory):
    """
    Find all CSV segments in a directory and merge them.

    Args:
        directory (str): Path to the directory containing decoded CSV files.

    Returns:
        pandas.DataFrame: Merged DataFrame, or None on failure.
    """
    import glob
    csv_paths = sorted(glob.glob(os.path.join(directory, '*.csv')))
    return merge_segments(csv_paths)


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------

def _sort_segments(csv_paths):
    """
    Sort segment files by the numeric extension index that blackbox_decode
    appends (e.g. '.01.csv', '.02.csv'). Falls back to plain sort.
    """
    def _segment_key(path):
        name = os.path.basename(path)
        # Typical pattern: NAME.01.csv, NAME.02.csv
        # Try to extract the numeric index before .csv
        stem = name.replace('.csv', '').replace('.CSV', '')
        parts = stem.rsplit('.', 1)
        if len(parts) == 2:
            try:
                return (parts[0], int(parts[1]))
            except ValueError:
                pass
        return (stem, 0)

    try:
        return sorted(csv_paths, key=_segment_key)
    except Exception:
        return sorted(csv_paths)


def _load_single(csv_path):
    """Load a single CSV, handling the optional 'H ' metadata header line."""
    try:
        with open(csv_path, 'r', encoding='utf-8') as f:
            first_line = f.readline()

        header_row = 1 if first_line.strip().startswith('H ') else 0
        df = pd.read_csv(csv_path, header=header_row, index_col=False,
                         low_memory=False, on_bad_lines='warn')
        df.columns = df.columns.str.strip()
        return df
    except Exception as e:
        print(f"  [merge] Error loading {os.path.basename(csv_path)}: {e}")
        return None


def _get_ordered_union_columns(dataframes):
    """
    Build the ordered union of all columns across DataFrames.
    Starts from the first DataFrame's column order and appends
    any new columns found in subsequent DataFrames.
    """
    seen = set()
    ordered = []
    for df in dataframes:
        for col in df.columns:
            if col not in seen:
                seen.add(col)
                ordered.append(col)
    return ordered


def _concat_with_time_offset(aligned_dfs):
    """
    Concatenate DataFrames, inserting time offsets so that time-like
    columns are monotonically increasing across segments.

    The time column is typically 'time (us)' in Betaflight CSVs.
    We also realign 'loopIteration' if present.
    """
    time_col = _find_column(aligned_dfs[0], ['time (us)', 'time(us)', 'time'])
    loop_col = _find_column(aligned_dfs[0], ['loopIteration', 'loop Iteration'])

    result_frames = []
    time_offset = 0
    loop_offset = 0

    for i, df in enumerate(aligned_dfs):
        df = df.copy()

        if i > 0:
            # Offset time
            if time_col and time_col in df.columns:
                first_time = df[time_col].dropna().iloc[0] if not df[time_col].dropna().empty else 0
                # Shift so this segment starts right after the previous one
                df[time_col] = df[time_col] - first_time + time_offset

            # Offset loop iterations
            if loop_col and loop_col in df.columns:
                first_loop = df[loop_col].dropna().iloc[0] if not df[loop_col].dropna().empty else 0
                df[loop_col] = df[loop_col] - first_loop + loop_offset

        result_frames.append(df)

        # Update offsets for the next segment
        if time_col and time_col in df.columns:
            last_time = df[time_col].dropna().iloc[-1] if not df[time_col].dropna().empty else 0
            # Add a small gap (1 microsecond) to avoid duplicate timestamps
            time_offset = last_time + 1

        if loop_col and loop_col in df.columns:
            last_loop = df[loop_col].dropna().iloc[-1] if not df[loop_col].dropna().empty else 0
            loop_offset = last_loop + 1

    merged = pd.concat(result_frames, ignore_index=True)
    return merged


def _find_column(df, candidates):
    """Find the first matching column name from a list of candidates."""
    for name in candidates:
        if name in df.columns:
            return name
    # Case-insensitive fallback
    lower_map = {c.lower(): c for c in df.columns}
    for name in candidates:
        if name.lower() in lower_map:
            return lower_map[name.lower()]
    return None
