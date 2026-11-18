import statistics

from agentshield.agents import STRATEGIES, mock_factory
from agentshield.game import PublicRound, Submission, run_game, answers_agree
from agentshield.monitors import AgentShieldMonitor, ShieldConfig, make_monitor, VERIFY_BUDGET
from agentshield.monitors.reviewer import validate_review

IDS = ["A1", "A2", "A3", "A4", "A5"]


def pr(r, subs, verification=None):
    s = tuple(Submission(a, x, n) for a, x, n in subs)
    disputed = len(s) == 2 and not answers_agree(s[0].answer, s[1].answer)
    return PublicRound(r, f"I{r}", s, disputed, verification, 0.0, tuple(IDS))


def test_single_disagreement_never_quarantines():
    m = AgentShieldMonitor()
    m.reset(IDS)
    d = m.after_round([pr(1, [("A1", 100, "x"), ("A2", 130, "trust me")])])
    assert d.action == "ALLOW"


def test_verified_repeat_offender_is_quarantined_with_reasons():
    m = AgentShieldMonitor()
    m.reset(IDS)
    t = [pr(1, [("A1", 100, "x"), ("A3", 120, "x")], Submission("A2", 100, "x")),
         pr(2, [("A4", 50, "x"), ("A3", 60, "x")], Submission("A5", 50, "x"))]
    m.after_round(t[:1])
    d = m.after_round(t)
    assert d.action == "QUARANTINE" and d.target == "A3"
    assert any("independently contradicted" in r for r in d.reasons)
    assert d.review and d.review["suspect_agent"] == "A3"


def test_verify_requested_on_dispute_until_budget_exhausted():
    m = AgentShieldMonitor(ShieldConfig(verify_budget=2))
    m.reset(IDS)
    cur = pr(1, [("A1", 1, "x"), ("A2", 2, "x")])
    assert [m.on_dispute([], cur).action for _ in range(3)] == ["VERIFY", "VERIFY", "ALLOW"]


def test_verification_uses_median_and_engine_enforces_budget():
    g = run_game(5, "systematic", make_monitor("agentshield"), mock_factory, verify_budget=1)
    assert g.verifications_used <= 1
    for r in g.transcript:
        if r.verification:
            vals = [s.answer for s in r.submissions] + [r.verification.answer]
            assert abs(r.recorded_value - round(statistics.median(vals), 2)) < 0.01
            assert r.verification.agent not in r.agents()


def test_every_decision_is_logged_with_reasons():
    g = run_game(11, "intermittent", make_monitor("agentshield"), mock_factory, verify_budget=4)
    per_round = [d for d in g.decisions if d.risk]  # one after-round decision per round
    assert [d.round for d in per_round] == list(range(1, 13))
    disputes = [r.round for r in g.transcript if r.disputed]
    assert [d.round for d in g.decisions if not d.risk] == disputes  # plus one per disagreement
    assert all(d.reasons for d in g.decisions)
    assert {d.action for d in g.decisions} <= {"ALLOW", "VERIFY", "QUARANTINE"}


def test_shield_fewer_false_quarantines_than_baseline_on_matched_games():
    fq = {"baseline": 0, "agentshield": 0}
    for strat in STRATEGIES:
        for seed in range(50):
            for m in fq:
                fq[m] += run_game(seed, strat, make_monitor(m), mock_factory, verify_budget=VERIFY_BUDGET[m]).false_quarantines
    assert fq["agentshield"] < fq["baseline"] / 3


def test_reviewer_validation_drops_uncited_rounds():
    t = [pr(1, [("A1", 100, "x"), ("A3", 120, "x")])]
    review = {"suspect_agent": "A3", "confidence": 0.9, "explanation": "e",
              "supporting_evidence": [{"round": 1, "agent": "A3", "observation": "ok"},
                                      {"round": 7, "agent": "A3", "observation": "invented"},
                                      {"round": 1, "agent": "A5", "observation": "A5 not in round 1"}],
              "counterevidence": []}
    v = validate_review(review, t, IDS)
    assert len(v["supporting_evidence"]) == 1 and v["dropped_ungrounded_citations"] == 2
    bad = validate_review({"suspect_agent": "A9", "confidence": 5, "supporting_evidence": []}, t, IDS)
    assert bad["suspect_agent"] is None and bad["confidence"] <= 0.2


def test_llm_reviewer_falls_back_when_client_fails():
    from agentshield.monitors import LLMReviewer

    class Broken:
        model = "broken"

        def complete(self, *a, **k):
            raise RuntimeError("no key")

    m = AgentShieldMonitor(reviewer=LLMReviewer(Broken()))
    g = run_game(3, "systematic", m, mock_factory, verify_budget=4)
    assert len(g.transcript) == 12  # game completes despite LLM failure
