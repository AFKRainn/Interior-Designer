"""
Entry point — launches the Streamlit application.
Usage: python run.py
"""
import subprocess
import sys
from pathlib import Path


def main():
    app_path = Path(__file__).parent / "app" / "ui" / "main.py"
    subprocess.run([
        sys.executable, "-m", "streamlit", "run",
        str(app_path),
        "--server.headless", "true",
        "--browser.gatherUsageStats", "false",
    ])


if __name__ == "__main__":
    main()
