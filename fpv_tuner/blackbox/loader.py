import pandas as pd
import subprocess
import tempfile
import os

def load_log(file_path):
    """
    Loads a Blackbox log file, decoding it if necessary.

    Args:
        file_path (str): The path to the log file (.csv, .bbl, .bfl).

    Returns:
        A tuple containing:
        - pd.DataFrame: The loaded data, or None on failure.
        - str: An error message if something went wrong, otherwise None.
    """
    file_ext = os.path.splitext(file_path)[1].lower()

    if file_ext == '.csv':
        df = _load_csv_log(file_path)
        if df is None:
            return None, "Failed to load CSV file."
        return df, None

    elif file_ext in ['.bbl', '.bfl']:
        temp_csv_path, error = _decode_blackbox_log(file_path)
        if error:
            return None, error

        df = _load_csv_log(temp_csv_path)

        # Clean up the temporary file
        try:
            os.remove(temp_csv_path)
        except OSError as e:
            print(f"Warning: Could not remove temporary file {temp_csv_path}: {e}")

        if df is None:
            return None, "Failed to parse the decoded CSV file."
        return df, None

    else:
        return None, f"Unsupported file type: {file_ext}"


def _decode_blackbox_log(file_path):
    """
    Decodes a binary Blackbox log file to a temporary CSV file.

    Returns:
        A tuple containing:
        - str: The path to the temporary CSV file, or None on failure.
        - str: An error message if something went wrong, otherwise None.
    """
    try:
        temp_dir = tempfile.gettempdir()
        # Create a unique name for the temp file
        temp_filename = f"fpv_tuner_decoded_{os.path.basename(file_path)}_{os.path.getmtime(file_path)}.csv"
        temp_csv_path = os.path.join(temp_dir, temp_filename)
    except Exception as e:
        return None, f"Failed to create temporary file path: {e}"

    # The command to execute
    command = ['blackbox_decode', file_path, '--output', temp_csv_path]

    try:
        print(f"Running command: {' '.join(command)}")
        process = subprocess.run(
            command,
            check=True,  # Raises CalledProcessError for non-zero exit codes
            capture_output=True,
            text=True,
            encoding='utf-8'
        )
        print("blackbox_decode successful.")
        return temp_csv_path, None
    except FileNotFoundError:
        error_msg = "'blackbox_decode' not found. Please ensure blackbox-tools is installed and in your system's PATH."
        print(f"Error: {error_msg}")
        return None, error_msg
    except subprocess.CalledProcessError as e:
        error_msg = f"Blackbox decoding failed with exit code {e.returncode}.\n\nStderr:\n{e.stderr}"
        print(error_msg)
        # Clean up the failed output file if it exists
        if os.path.exists(temp_csv_path):
            os.remove(temp_csv_path)
        return None, error_msg
    except Exception as e:
        error_msg = f"An unexpected error occurred during decoding: {e}"
        print(error_msg)
        if os.path.exists(temp_csv_path):
            os.remove(temp_csv_path)
        return None, error_msg


def _load_csv_log(file_path):
    """
    Loads a Blackbox CSV log file into a pandas DataFrame.
    (Renamed to be a "private" function)
    """
    try:
        # Check if the file is empty first, as pandas might not handle it gracefully
        if os.path.getsize(file_path) == 0:
            print(f"Warning: CSV file is empty: {file_path}")
            return None

        df = pd.read_csv(file_path, header=0, index_col=False, low_memory=False, on_bad_lines='skip')

        # Betaflight logs often have headers starting with 'H'.
        # The real header is the next line.
        if df.columns[0].strip().upper() == 'H':
            df = pd.read_csv(file_path, header=1, index_col=False, low_memory=False, on_bad_lines='skip')
            df.columns = df.columns.str.strip()

        print(f"Successfully loaded {file_path}")
        return df
    except Exception as e:
        print(f"Error loading CSV file {file_path}: {e}")
        return None
