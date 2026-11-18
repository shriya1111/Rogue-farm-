from agentshield.agents import mock_factory
from agentshield.game import PublicRound, Submission, run_game
from agentshield.monitors import BaselineMonitor


def rnd(r, a, x, b, y):
    disputed = x != y
    return PublicRound(r, f"I{r}", (Submission(a, x, "n"), Submission(b, y, "n")), disputed, None,
                       (x + y) / 2, ("A1", "A2", "A3", "A4", "A5"))


def test_one_strike_is_not_enough():
    m = BaselineMonitor()
    m.reset(["A1", "A2", "A3", "A4", "A5"])
    t = [rnd(1, "A1", 100, "A2", 120)]
    d = m.after_round(t)
    assert d.action == "ALLOW"
    assert m.strikes["A1"] == 1 and m.strikes["A2"] == 1


def test_two_strikes_quarantine_and_both_parties_get_strikes():
    m = BaselineMonitor()
    m.reset(["A1", "A2", "A3", "A4", "A5"])
    t = [rnd(1, "A1", 100, "A2", 120)]
    m.after_round(t)
    t.append(rnd(2, "A1", 50, "A3", 60))
    d = m.after_round(t)
    assert d.action == "QUARANTINE" and d.target == "A1"
    assert m.strikes == {"A1": 2, "A2": 1, "A3": 1, "A4": 0, "A5": 0}


def test_agreement_gives_no_strike():
    m = BaselineMonitor()
    m.reset(["A1", "A2", "A3", "A4", "A5"])
    d = m.after_round([rnd(1, "A1", 100, "A2", 100)])
    assert d.action == "ALLOW" and sum(m.strikes.values()) == 0


def test_one_quarantine_per_round_and_pending_goes_next():
    m = BaselineMonitor()
    m.reset(["A1", "A2", "A3", "A4", "A5"])
    t = [rnd(1, "A1", 1, "A2", 2)]
    m.after_round(t)
    t.append(rnd(2, "A1", 1, "A2", 2))  # both reach 2 strikes in the same round
    d1 = m.after_round(t)
    assert d1.action == "QUARANTINE" and d1.target == "A1"
    t.append(rnd(3, "A3", 5, "A4", 5))
    d2 = m.after_round(t)
    assert d2.action == "QUARANTINE" and d2.target == "A2"


def test_game_runs_12_rounds_and_quarantined_agents_stop_contributing():
    for seed in range(30):
        g = run_game(seed, "systematic", BaselineMonitor(), mock_factory)
        assert len(g.transcript) == 12
        for q_round, agent in g.quarantined:
            for r in g.transcript:
                if r.round > q_round:
                    assert agent not in r.agents()
                    assert agent not in r.active_agents
