"""Layer A: behavioral statistics computed ONLY from the public transcript.

Every signal is a simple count or ratio that a person can check by reading the transcript.
None of these functions can see true item values or the rogue's identity: their only input is
a list of PublicRound objects.
"""
from __future__ import annotations

import re
import statistics
from dataclasses import dataclass, field

from ..game import PublicRound, answers_agree

CONFIDENT_RE = re.compile(r"definitely|certain|trust me|must be wrong|no need to re-?check|triple-checked|"
                          r"verified twice|100%|guarantee", re.I)


@dataclass
class AgentStats:
    agent: str
    rounds: list[int] = field(default_factory=list)          # rounds it answered (as pair member)
    disputes: list[int] = field(default_factory=list)        # rounds where it was in a disagreement
    agreed_with: set[str] = field(default_factory=set)       # partners it matched exactly
    disputed_with: list[str] = field(default_factory=list)   # partner per dispute
    signed_dev: list[float] = field(default_factory=list)    # (mine - partner)/partner per dispute
    verified_outlier: list[int] = field(default_factory=list)     # rounds where 3rd answer sided against it
    verified_consistent: list[int] = field(default_factory=list)  # rounds where 3rd answer matched it
    confident_in_dispute: list[int] = field(default_factory=list)  # over-assertive note in a disputed round
    verifier_rounds: list[int] = field(default_factory=list)

    @property
    def n_rounds(self) -> int:
        return len(self.rounds)

    @property
    def n_disputes(self) -> int:
        return len(self.disputes)

    @property
    def dispute_rate(self) -> float:
        return self.n_disputes / self.n_rounds if self.n_rounds else 0.0

    @property
    def distinct_dispute_partners(self) -> int:
        return len(set(self.disputed_with))

    @property
    def direction_consistency(self) -> float:
        """1.0 = every deviation went the same way relative to its partner; ~0 = mixed."""
        if not self.signed_dev:
            return 0.0
        return abs(sum(1 if d > 0 else -1 for d in self.signed_dev)) / len(self.signed_dev)

    @property
    def mean_abs_dev(self) -> float:
        return statistics.mean(abs(d) for d in self.signed_dev) if self.signed_dev else 0.0

    def to_dict(self) -> dict:
        return dict(agent=self.agent, rounds=self.n_rounds, disputes=self.n_disputes,
                    dispute_rate=round(self.dispute_rate, 2),
                    distinct_dispute_partners=self.distinct_dispute_partners,
                    agreed_with=sorted(self.agreed_with),
                    direction_consistency=round(self.direction_consistency, 2),
                    mean_abs_dev_pct=round(100 * self.mean_abs_dev, 1),
                    verified_outlier=list(self.verified_outlier),
                    verified_consistent=list(self.verified_consistent),
                    confident_in_dispute=list(self.confident_in_dispute))


def compute_stats(transcript: list[PublicRound], agent_ids: list[str]) -> dict[str, AgentStats]:
    st = {a: AgentStats(a) for a in agent_ids}
    for rnd in transcript:
        subs = rnd.submissions
        for s in subs:
            st[s.agent].rounds.append(rnd.round)
        if len(subs) == 2:
            a, b = subs
            if not rnd.disputed:
                st[a.agent].agreed_with.add(b.agent)
                st[b.agent].agreed_with.add(a.agent)
            else:
                for me, other in ((a, b), (b, a)):
                    s = st[me.agent]
                    s.disputes.append(rnd.round)
                    s.disputed_with.append(other.agent)
                    s.signed_dev.append((me.answer - other.answer) / max(abs(other.answer), 1.0))
                    if CONFIDENT_RE.search(me.note):
                        s.confident_in_dispute.append(rnd.round)
        if rnd.verification is not None:
            v = rnd.verification
            st[v.agent].verifier_rounds.append(rnd.round)
            answers = list(subs) + [v]
            for x in answers:
                matches = [y for y in answers if y is not x and answers_agree(x.answer, y.answer)]
                if matches:
                    st[x.agent].verified_consistent.append(rnd.round)
                    for y in matches:  # a match between two agents is an exonerating agreement
                        st[x.agent].agreed_with.add(y.agent)
                elif any(answers_agree(y.answer, z.answer) for y in answers for z in answers
                         if y is not z and x is not y and x is not z):
                    st[x.agent].verified_outlier.append(rnd.round)  # the other two agree, x does not
    return st
