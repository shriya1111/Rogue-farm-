#!/usr/bin/env python3
"""Track 2 ledger game.

  python sim.py --mock --games 200            # 200 scripted games per rogue strategy, seconds, no key
  python sim.py --mock --seed 7 --show        # print one transcript with monitor decisions
  python sim.py --real --games 5              # real Claude agents (needs ANTHROPIC_API_KEY)
  python sim.py --real --provider gemini      # or another provider

Real mode puts a different Claude model in each agent seat (see agents.DEFAULT_AGENT_MODELS).
Transcripts from real games are cached in results/real_games/.
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from agentshield.agents import DEFAULT_AGENT_MODELS, STRATEGIES, make_llm_factory, mock_factory
from agentshield.evaluate import aggregate
from agentshield.game import run_game
from agentshield.llm import detect_provider, get_client, LLMUnavailable
from agentshield.monitors import VERIFY_BUDGET, LLMReviewer, make_monitor

ROOT = Path(__file__).resolve().parent


def show(g) -> None:
    print(f"\nGame seed={g.seed} strategy={g.strategy} monitor={g.monitor}  (rogue revealed after play: {g.rogue})")
    dec = {}
    for d in g.decisions:
        dec.setdefault(d.round, []).append(d)
    for r in g.transcript:
        subs = " | ".join(f"{s.agent}: {s.answer:>9.2f}  \"{s.note}\"" for s in r.submissions)
        flag = "DISAGREE" if r.disputed else "agree"
        print(f"R{r.round:>2} {flag:<8} {subs}")
        if r.verification:
            print(f"    VERIFY by {r.verification.agent}: {r.verification.answer:.2f} -> ledger records {r.recorded_value}")
        for d in dec.get(r.round, []):
            if d.action != "ALLOW" or r.disputed:
                print(f"    [{d.action}{' ' + d.target if d.target else ''}] {d.reasons[0]}")
    print(f"Result: caught={g.rogue_caught} round={g.round_caught} false_quarantines={g.false_quarantines} "
          f"ledger_error=${g.ledger_error:.2f} ({g.ledger_error_pct:.2f}%)")


def main(argv=None):
    ap = argparse.ArgumentParser()
    mode = ap.add_mutually_exclusive_group()
    mode.add_argument("--mock", action="store_true", help="scripted agents (default)")
    mode.add_argument("--real", action="store_true", help="LLM agents")
    ap.add_argument("--games", type=int, default=None)
    ap.add_argument("--seed", type=int, default=None, help="play one specific seed")
    ap.add_argument("--strategy", choices=STRATEGIES, default=None)
    ap.add_argument("--monitor", default="both", choices=["both", "baseline", "agentshield"])
    ap.add_argument("--provider", default=None, help="anthropic | gemini | openrouter")
    ap.add_argument("--llm-review", action="store_true", help="use an LLM evidence reviewer (needs a provider)")
    ap.add_argument("--reviewer-model", default="claude-opus-5-5")
    ap.add_argument("--show", action="store_true", help="print transcripts")
    args = ap.parse_args(argv)

    provider = args.provider or detect_provider()
    cache_file = ROOT / "results" / "real_games" / f"answer_cache_{args.strategy or 'mixed'}.json"
    if args.real:
        if not provider:
            sys.exit("Real mode needs an LLM provider (set ANTHROPIC_API_KEY). Use --mock to run without one.")
        cache = json.loads(cache_file.read_text()) if cache_file.exists() else {}
        factory = make_llm_factory(provider, cache=cache)
        n = args.games or 5
        print(f"REAL mode via {provider}; agent models: {DEFAULT_AGENT_MODELS if provider == 'anthropic' else 'provider default'}")
    else:
        factory, n = mock_factory, args.games or 200

    reviewer = None
    if args.llm_review:
        try:
            reviewer = LLMReviewer(get_client(provider or "anthropic", args.reviewer_model))
        except LLMUnavailable as e:
            print(f"LLM reviewer unavailable ({e}); using heuristic reviewer.")

    monitors = ["baseline", "agentshield"] if args.monitor == "both" else [args.monitor]
    strategies = [args.strategy] if args.strategy else list(STRATEGIES)
    seeds = [args.seed] if args.seed is not None else list(range(20000, 20000 + n))
    if args.real and not args.strategy:
        plan = [(STRATEGIES[i % len(STRATEGIES)], s) for i, s in enumerate(seeds)]  # n games total, mixed rogues
    elif args.seed is not None:
        plan = [(strategies[0], args.seed)]
    else:
        plan = [(st, s) for st in strategies for s in seeds]
    rows = {m: [] for m in monitors}
    cache = ROOT / "results" / "real_games"
    cache.mkdir(parents=True, exist_ok=True)
    for strat, seed in plan:
        if True:
            for m in monitors:
                mon = make_monitor(m, reviewer=reviewer if m == "agentshield" else None)
                g = run_game(seed, strat, mon, factory, verify_budget=VERIFY_BUDGET[m])
                rows[m].append(g.summary())
                if args.show or args.seed is not None:
                    show(g)
                if args.real:
                    cache.mkdir(parents=True, exist_ok=True)
                    (cache / f"{strat}_{seed}_{m}.json").write_text(json.dumps({
                        "summary": g.summary(), "transcript": [r.to_dict() for r in g.transcript],
                        "decisions": [d.__dict__ for d in g.decisions], "item_truth": g.item_truth,
                        "agent_models": DEFAULT_AGENT_MODELS if provider == "anthropic" else provider}, indent=1, default=str))
                    cache_file.write_text(json.dumps(factory.cache))
    print(f"\n{'monitor':<14}{'games':>6}{'catch%':>8}{'med.round':>10}{'FQ/game':>9}{'ledger err $':>13}")
    for m, rs in rows.items():
        a = aggregate(rs)
        print(f"{m:<14}{a['games']:>6}{a['catch_rate']:>8}{str(a['median_round_caught']):>10}"
              f"{a['false_quarantines_per_game']:>9}{a['mean_ledger_error']:>13}")


if __name__ == "__main__":
    main()
