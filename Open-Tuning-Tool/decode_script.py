import subprocess
import sys
import os
import glob

def decode_log(input_path):
    """
    A simple script to decode a single Blackbox log file.
    """
    if not os.path.exists(input_path):
        print(f"Error: Input file not found at '{input_path}'")
        return

    input_dir = os.path.dirname(input_path)
    print(f"Attempting to decode: {input_path}")
    print(f"Output CSVs will be saved in the same folder: {input_dir}")

    command = ['blackbox_decode', input_path]

    try:
        process = subprocess.run(
            command,
            capture_output=True,
            text=True,
            check=True
        )

        print("\n--- blackbox_decode STDOUT ---")
        print(process.stdout or "No standard output.")
        print("--- blackbox_decode STDERR ---")
        print(process.stderr or "No standard error.")
        print("------------------------------")
        print("✅ blackbox_decode process finished successfully.")

        base_name = os.path.splitext(os.path.basename(input_path))[0]
        found_files = glob.glob(os.path.join(input_dir, f"{base_name}*.csv"))

        if found_files:
            print(f"✅ Success! Found decoded file(s):")
            for f in found_files:
                print(f"  - {f}")
            print(f"\nYou can now open '{found_files[0]}' to inspect the headers.")
        else:
            print("⚠️ Warning: Process finished, but no output CSV file was found in the source directory.")

    except FileNotFoundError:
        print("❌ Error: 'blackbox_decode' command not found. Is it in your system's PATH?")
    except subprocess.CalledProcessError as e:
        print(f"❌ Error: blackbox_decode failed with exit code {e.returncode}.")
        print("\n--- blackbox_decode STDOUT ---")
        print(e.stdout or "No standard output.")
        print("--- blackbox_decode STDERR ---")
        print(e.stderr or "No standard error.")
        print("------------------------------")
    except Exception as e:
        print(f"❌ An unexpected Python error occurred: {e}")


if __name__ == "__main__":
    if len(sys.argv) != 2:
        print("Usage: python3 decode_script.py <path_to_your_bbl_file>")
    else:
        decode_log(sys.argv[1])
