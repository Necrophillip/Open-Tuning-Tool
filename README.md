# FPV Blackbox Tuner

A cross-platform desktop application for analyzing and tuning FPV drones using Betaflight Blackbox logs. Built with Python, PyQt6, and pyqtgraph.

## Features

- **Universal Log Support**: Load raw binary logs (`.BBL`, `.BFL`) and decoded CSV logs. The application integrates with `blackbox_decode` for on-the-fly decoding.
- **Multi-Log Comparison**: Load multiple logs simultaneously to visually compare "before and after" tuning changes.
- **Intuitive Tabbed Interface**:
    - **Trace Viewer**: A simple view for inspecting raw gyro and RC command data.
    - **Noise Analysis**: Analyze gyro and D-term noise with interactive time-series traces and Power Spectral Density (PSD) plots to fine-tune your filters.
    - **Step Response Analysis**: Automatically detect and inspect step responses to effectively tune your PID gains for Roll, Pitch, and Yaw.
- **High Performance**: Built with `pyqtgraph` and optimized for performance, ensuring smooth plotting and a responsive UI even with very large log files.
- **User-Friendly**: Features a file manager for loaded logs, asynchronous file loading that doesn't freeze the UI, and a status bar for feedback.

## Requirements

1.  **Python 3.8+**
2.  **Python Libraries**: See `requirements.txt`. These can be installed via pip.
3.  **`blackbox-tools`**: The `blackbox_decode` utility is required for opening binary `.BBL` and `.BFL` files.
    -   **Installation**: Download the appropriate `blackbox-tools` executable for your operating system from the official [Betaflight Blackbox Log Viewer releases page](https://github.com/betaflight/blackbox-log-viewer/releases).
    -   **Configuration**: Ensure the `blackbox_decode` executable is placed in a directory that is included in your system's `PATH` environment variable so that it can be called from any terminal.

## Installation & Usage

1.  **Clone the repository:**
    ```bash
    git clone https://github.com/your-username/fpv-blackbox-tuner.git
    cd fpv-blackbox-tuner
    ```

2.  **Install `blackbox-tools`**:
    -   Download and place the executable in your system's PATH as described in the Requirements section.

3.  **Install Python dependencies:**
    -   It's highly recommended to use a virtual environment.
    ```bash
    python -m venv venv
    source venv/bin/activate  # On Windows, use `venv\Scripts\activate`
    ```
    -   Install the required libraries:
    ```bash
    pip install -r requirements.txt
    ```

4.  **Run the application:**
    -   From the root directory of the project, run the main module:
    ```bash
    python -m fpv_tuner.main
    ```

## Project Structure

The project is organized into a modular package structure to promote scalability and maintainability:

-   `fpv_tuner/`
    -   `main.py`: The main entry point of the application.
    -   `analysis/`: Contains all the data processing and calculation logic (PSD, step response detection, etc.).
    -   `blackbox/`: Handles loading and decoding of Blackbox files.
    -   `gui/`: Contains all PyQt6 GUI components, with each tab and major widget in its own module.
        -   `main_window.py`: The main application window and layout manager.
        -   `worker.py`: The QThread worker for non-blocking file loading.
        -   `*_tab.py`: Each file defines a specific tab in the UI.
-   `requirements.txt`: Lists all Python dependencies.
-   `README.md`: This file.
