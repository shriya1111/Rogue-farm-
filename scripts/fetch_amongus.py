#!/usr/bin/env python3
"""Download a small, practical sample of the AmongUs sandbox logs (dataset id `amongus-sandbox`).

Source: https://huggingface.co/datasets/7vik/amongus (published by github.com/7vik/AmongUs).
Default: two experiments (Llama-vs-Llama and Llama-impostor vs Phi-crew), 200 games, ~130 MB.
Files land in data/amongus/raw/<experiment>/ (git-ignored).
"""
import argparse
import sys
import urllib.request
from pathlib import Path

BASE = "https://huggingface.co/datasets/7vik/amongus/resolve/main/expt-logs"
EXPERIMENTS = ["2025-02-01_llama_llama_100_games_v3", "2025-02-01_llama_phi_100_games_v3",
               "2025-02-01_phi_llama_100_games_v3", "2025-02-01_phi_phi_100_games_v3"]
FILES = ["experiment-details.txt", "summary.json", "agent-logs-compact.json"]
DEST = Path(__file__).resolve().parent.parent / "data" / "amongus" / "raw"


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--experiments", type=int, default=2, help="how many of the 4 experiments (100 games each)")
    args = ap.parse_args()
    for exp in EXPERIMENTS[: args.experiments]:
        d = DEST / exp
        d.mkdir(parents=True, exist_ok=True)
        for f in FILES:
            out = d / f
            if out.exists() and out.stat().st_size > 0:
                print(f"have {out}")
                continue
            print(f"downloading {exp}/{f} ...", flush=True)
            try:
                urllib.request.urlretrieve(f"{BASE}/{exp}/{f}", out)
            except Exception as e:
                sys.exit(f"Download failed ({e}). Is huggingface.co reachable from this network?")
    print("done")


if __name__ == "__main__":
    main()
