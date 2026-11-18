#!/usr/bin/env python3
"""One-command demo:  python run_demo.py

Runs the 200-game-per-strategy mock evaluation if results are missing (about 5 seconds, no API key),
then launches the Streamlit dashboard."""
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent
if not (ROOT / "results" / "eval_summary.json").exists():
    print("No evaluation results yet; running 200 matched mock games per strategy ...")
    subprocess.check_call([sys.executable, "-m", "agentshield.evaluate", "--games", "200"], cwd=ROOT)
if not (ROOT / "results" / "dev_sweep.json").exists():
    subprocess.check_call([sys.executable, "scripts/dev_sweep.py"], cwd=ROOT)
sys.exit(subprocess.call([sys.executable, "-m", "streamlit", "run", str(ROOT / "dashboard" / "app.py"),
                          "--server.headless", "true", *sys.argv[1:]], cwd=ROOT))
