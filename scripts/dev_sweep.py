#!/usr/bin/env python3
"""Catch-rate vs false-accusation tradeoff for AgentShield settings, on DEV seeds only.
Writes results/dev_sweep.json (shown in the dashboard). The shipped defaults are budget=4, threshold=55."""
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from agentshield.agents import STRATEGIES, mock_factory  # noqa: E402
from agentshield.evaluate import DEV_SEEDS, aggregate, RESULTS  # noqa: E402
from agentshield.game import run_game  # noqa: E402
from agentshield.monitors import AgentShieldMonitor, ShieldConfig  # noqa: E402

rows = []
for budget in (0, 2, 3, 4, 5, 6):
    for thr in (45, 55, 65):
        games = [run_game(seed, s, AgentShieldMonitor(ShieldConfig(verify_budget=budget, quarantine_threshold=thr,
                                                                    use_verify=budget > 0)),
                          mock_factory, verify_budget=budget).summary()
                 for s in STRATEGIES for seed in DEV_SEEDS]
        a = aggregate(games)
        rows.append({"verify_budget": budget, "threshold": thr, "games": a["games"], "catch %": a["catch_rate"],
                     "median round": a["median_round_caught"], "false Q / game": a["false_quarantines_per_game"],
                     "mean ledger err $": a["mean_ledger_error"], "default": budget == 4 and thr == 55})
        print(rows[-1])
RESULTS.mkdir(exist_ok=True)
(RESULTS / "dev_sweep.json").write_text(json.dumps(rows, indent=1))
