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

def parse_pid_data_from_headers(headers):
    """
    Parses the 'P,I,D,F' string from the headers dictionary to extract PID values.
    """
    pid_header = headers.get('P,I,D,F')
    if not pid_header:
        return {}

    values = [int(v) for v in pid_header.split(',')]
    pids = {}

    keys = [
        'p_roll', 'i_roll', 'd_roll', 'f_roll',
        'p_pitch', 'i_pitch', 'd_pitch', 'f_pitch',
        'p_yaw', 'i_yaw', 'd_yaw', 'f_yaw'
    ]

    # Handle cases where the header might be incomplete
    num_values = len(values)
    for i, key in enumerate(keys):
        if i < num_values:
            pids[key] = values[i]
        else:
            pids[key] = 0 # Default to 0 if not present

    return pids
