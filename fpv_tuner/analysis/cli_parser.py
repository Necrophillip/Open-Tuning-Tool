import re

def parse_pids_from_cli(cli_content: str) -> dict:
    """
    Parses PID controller values from a Betaflight CLI dump.

    This function searches for 'p_roll', 'i_roll', 'd_roll', etc., and
    extracts their integer values.

    Args:
        cli_content: A string containing the output of a 'dump' or 'diff'
                     command from the Betaflight CLI.

    Returns:
        A dictionary with the parsed PID values, structured by axis and term.
        Example:
        {
            'roll': {'p': 45, 'i': 85, 'd': 38},
            'pitch': {'p': 55, 'i': 90, 'd': 42},
            'yaw': {'p': 70, 'i': 45, 'd': 0}
        }
    """
    pids = {}
    # Regex to find "set <pid_term> = <value>" and capture term and value
    # It handles terms like 'p_roll', 'i_pitch', 'd_yaw'
    pattern = re.compile(r"set\s+([pid])_([a-zA-Z]+)\s*=\s*(\d+)")

    matches = pattern.findall(cli_content)

    for term, axis, value in matches:
        axis = axis.lower()
        if axis not in pids:
            pids[axis] = {}
        # We need to map the first letter to the term
        term_map = {'p': 'p', 'i': 'i', 'd': 'd'}
        pid_term = term_map.get(term)
        if pid_term:
            pids[axis][pid_term] = int(value)

    # A second regex for the 'f' terms, which are separate
    pattern_f = re.compile(r"set\s+f_([a-zA-Z]+)\s*=\s*(\d+)")
    matches_f = pattern_f.findall(cli_content)
    for axis, value in matches_f:
        axis = axis.lower()
        if axis not in pids:
            pids[axis] = {}
        pids[axis]['f'] = int(value)

    return pids