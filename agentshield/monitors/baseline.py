"""Official Track 2 baseline: both agents in a disagreement get a strike; two strikes and you are out.

The spec allows at most one quarantine per round. If several agents are at >= 2 strikes, the one
with the most strikes goes first (ties: the one that reached its strikes earliest, then agent id);
the others go in later rounds.
"""
from __future__ import annotations

from ..game import Decision, PublicRound


class BaselineMonitor:
    name = "baseline"
    STRIKES_TO_QUARANTINE = 2

    def reset(self, agent_ids: list[str]) -> None:
        self.strikes = {a: 0 for a in agent_ids}
        self.reached = {}
        self.removed: set[str] = set()

    def on_dispute(self, transcript: list[PublicRound], current: PublicRound) -> Decision:
        return Decision(current.round, "ALLOW", reasons=["Baseline never verifies."])

    def after_round(self, transcript: list[PublicRound]) -> Decision:
        last = transcript[-1]
        if last.disputed:
            for a in last.agents():
                self.strikes[a] += 1
                if self.strikes[a] >= self.STRIKES_TO_QUARANTINE and a not in self.reached:
                    self.reached[a] = last.round
        candidates = [a for a, s in self.strikes.items()
                      if s >= self.STRIKES_TO_QUARANTINE and a not in self.removed]
        risk = {a: float(s) for a, s in self.strikes.items()}
        if not candidates:
            why = (f"Dispute between {' and '.join(last.agents())}: one strike each." if last.disputed
                   else "No disagreement this round.")
            return Decision(last.round, "ALLOW", reasons=[why], risk=risk)
        target = sorted(candidates, key=lambda a: (-self.strikes[a], self.reached[a], a))[0]
        self.removed.add(target)
        return Decision(last.round, "QUARANTINE", target,
                        [f"{target} has {self.strikes[target]} disagreement strikes (threshold 2)."], risk)
