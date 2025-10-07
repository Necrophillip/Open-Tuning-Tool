def get_blackbox_headers(file_path):
    """
    Reads the first few lines of a decoded Blackbox CSV file to extract
    key metadata headers.

    Returns:
        A dictionary containing the parsed header values.
    """
    headers = {}
    try:
        with open(file_path, 'r', encoding='utf-8') as f:
            # Read up to the first 20 lines, which should contain all headers
            for _ in range(20):
                line = f.readline().strip()
                if not line:
                    break

                # Betaflight headers start with "H "
                if line.startswith('H '):
                    line = line[2:] # Remove the prefix
                    if ':' in line:
                        key, value = line.split(':', 1)
                        headers[key.strip()] = value.strip()
    except Exception as e:
        print(f"Could not read blackbox headers from {file_path}: {e}")

    return headers

def parse_pid_data_from_headers(headers: dict) -> dict:
    """
    Parses PID values from a dictionary of Blackbox headers.
    """
    pids = {}
    for key, value in headers.items():
        # Keys are expected to be like 'p_roll', 'i_pitch', etc.
        parts = key.split('_')
        if len(parts) == 2 and parts[0] in ['p', 'i', 'd', 'f']:
            term, axis = parts
            axis = axis.lower()
            if axis not in pids:
                pids[axis] = {}

            try:
                pids[axis][term] = int(value)
            except (ValueError, TypeError):
                print(f"Warning: Could not parse PID value for key '{key}' with value '{value}'")

    return pids
