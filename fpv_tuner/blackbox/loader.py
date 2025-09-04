import pandas as pd
import subprocess
import tempfile
import os
import glob
import shutil

def load_log(file_path):
    """
    Loads a Blackbox log file, decoding it if necessary.

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
        temp_csv_path, temp_dir, error = _decode_blackbox_log(file_path)

        if error:
            if temp_dir and os.path.exists(temp_dir):
                shutil.rmtree(temp_dir, ignore_errors=True)
            return None, error

        df = _load_csv_log(temp_csv_path)

        # Clean up the temporary directory
        if temp_dir and os.path.exists(temp_dir):
            shutil.rmtree(temp_dir, ignore_errors=True)

        if df is None:
            return None, "Failed to parse the decoded CSV file."
        return df, None

    else:
        return None, f"Unsupported file type: {file_ext}"


def _decode_blackbox_log(file_path):
    """
    Decodes a binary Blackbox log file to a temporary CSV file inside a temporary directory.

    Returns:
        A tuple containing:
        - str: The path to the temporary CSV file, or None on failure.
        - str: The path to the temporary directory for cleanup, or None.
        - str: An error message if something went wrong, otherwise None.
    """
    temp_dir = None
    try:
        temp_dir = tempfile.mkdtemp(prefix="fpv_tuner_")
    except Exception as e:
        return None, None, f"Failed to create temporary directory: {e}"

    command = ['blackbox_decode', file_path, '--output-dir', temp_dir]

    try:
        print(f"Running command: {' '.join(command)}")
        process = subprocess.run(
            command,
            check=True,
            capture_output=True,
            text=True,
            encoding='utf-8'
        )
        print("blackbox_decode process finished.")

        # Find the created CSV file(s) in the temp directory
        csv_files = glob.glob(os.path.join(temp_dir, '*.csv'))

        if not csv_files:
            error_msg = ("Decoding process finished but produced no output file. "
                         "The log file may be empty, corrupt, or in an unsupported format.\n\n"
                         f"Stderr from blackbox_decode:\n{process.stderr}")
            return None, temp_dir, error_msg

        # For multi-log BBL files, this would need to be more sophisticated.
        # For now, we'll just work with the first log found.
        decoded_csv_path = csv_files[0]
        print(f"Successfully decoded log file to: {decoded_csv_path}")
        return decoded_csv_path, temp_dir, None

    except FileNotFoundError:
        error_msg = "'blackbox_decode' not found. Please ensure blackbox-tools is installed and in your system's PATH."
        return None, temp_dir, error_msg
    except subprocess.CalledProcessError as e:
        error_msg = f"Blackbox decoding failed with exit code {e.returncode}.\n\nStderr:\n{e.stderr}"
        return None, temp_dir, error_msg
    except Exception as e:
        error_msg = f"An unexpected error occurred during decoding: {e}"
        return None, temp_dir, error_msg


def _load_csv_log(file_path):
    """
    Loads a Blackbox CSV log file into a pandas DataFrame.
    (Renamed to be a "private" function)
    """
    try:
        if not os.path.exists(file_path) or os.path.getsize(file_path) == 0:
            print(f"Warning: CSV file is empty or does not exist: {file_path}")
            return None

        df = pd.read_csv(file_path, header=0, index_col=False, low_memory=False, on_bad_lines='skip')

        if df.columns[0].strip().upper() == 'H':
            df = pd.read_csv(file_path, header=1, index_col=False, low_memory=False, on_bad_lines='skip')
            df.columns = df.columns.str.strip()

        print(f"Successfully loaded {os.path.basename(file_path)}")
        return df
    except Exception as e:
        print(f"Error loading CSV file {file_path}: {e}")
        return None
