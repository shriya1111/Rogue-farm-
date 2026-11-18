"""Data-leakage prevention: monitors must never see hidden roles or true values."""
import dataclasses
import json

from agentshield import amongus
from agentshield.agents import mock_factory
from agentshield.game import PublicRound, Submission, make_items, run_game
from agentshield.monitors import make_monitor, VERIFY_BUDGET

FORBIDDEN_FIELDS = {"true_value", "is_rogue", "rogue", "strategy", "qty", "unit_price", "fee", "description"}


class SpyMonitor:
    """Wraps a monitor and records every object it is given."""

    def __init__(self, inner):
        self.inner, self.name, self.seen = inner, inner.name, []

    def reset(self, ids):
        self.seen.append(("reset", list(ids)))
        self.inner.reset(ids)

    def on_dispute(self, transcript, current):
        self.seen.append(("dispute", list(transcript), current))
        return self.inner.on_dispute(transcript, current)

    def after_round(self, transcript):
        self.seen.append(("after", list(transcript)))
        return self.inner.after_round(transcript)


def _walk(o):
    if isinstance(o, (list, tuple)):
        for x in o:
            yield from _walk(x)
    elif dataclasses.is_dataclass(o):
        yield o
        for f in dataclasses.fields(o):
            yield from _walk(getattr(o, f.name))


def test_monitor_only_receives_public_types():
    for name in ("baseline", "agentshield"):
        spy = SpyMonitor(make_monitor(name))
        run_game(1, "systematic", spy, mock_factory, verify_budget=VERIFY_BUDGET[name])
        for call in spy.seen:
            for obj in _walk(call[1:]):
                assert type(obj) in (PublicRound, Submission), type(obj)
                assert not FORBIDDEN_FIELDS & {f.name for f in dataclasses.fields(obj)}


def test_public_round_has_no_truth_fields():
    names = {f.name for f in dataclasses.fields(PublicRound)} | {f.name for f in dataclasses.fields(Submission)}
    assert not FORBIDDEN_FIELDS & names


def test_true_values_never_appear_in_monitor_inputs():
    seed = 2
    truths = {f"{i.true_value:.2f}" for i in make_items(seed)}
    spy = SpyMonitor(make_monitor("agentshield"))
    g = run_game(seed, "systematic", spy, mock_factory, verify_budget=4)
    # A truth can appear only as an agent's posted answer (honest agents post it), never as a separate field.
    posted = {f"{s.answer:.2f}" for r in g.transcript for s in r.submissions + ((r.verification,) if r.verification else ())}
    blob = json.dumps([[r.to_dict() for r in c[1]] for c in spy.seen if c[0] == "after"])
    for t in truths - posted:
        assert t not in blob


def test_decisions_invariant_to_hidden_rogue_label():
    """Same public transcript -> same decisions, whatever the hidden rogue identity is."""
    g = run_game(4, "systematic", make_monitor("agentshield"), mock_factory, verify_budget=4)
    replay = make_monitor("agentshield")
    replay.reset(["A1", "A2", "A3", "A4", "A5"])
    replayed = [(d.action, d.target) for d in
                (replay.after_round(g.transcript[: i + 1]) for i in range(len(g.transcript)))]
    original = [(d.action, d.target) for d in g.decisions if d.risk]  # after-round decisions carry risk
    assert replayed == original
    # The replay never had access to g.rogue, g.item_truth or the agents: decisions are a pure
    # function of the public transcript.


def test_amongus_public_extraction_strips_private_fields():
    rec = {"game_index": "Game 1", "step": 3,
           "player": {"name": "Player 2: red", "identity": "Impostor", "model": "m", "location": "Admin"},
           "interaction": {"system_prompt": "You are an Impostor. SECRET",
                           "prompt": {"All Info": "You killed Player 4", "Memory": "I am the impostor"},
                           "response": {"Thinking Process": "As the Impostor I will lie",
                                        "Condensed Memory": "impostor plan",
                                        "Action": 'SPEAK: "I was in Admin doing tasks."'}}}
    kill = dict(rec, interaction=dict(rec["interaction"], response={"Action": "KILL Player 4: blue"}))
    games = amongus.extract_public_events([rec, kill])
    evs = games["Game 1"]
    assert len(evs) == 1  # the KILL action is private and dropped
    blob = json.dumps([dataclasses.asdict(e) for e in evs])
    for secret in ("Impostor", "SECRET", "killed", "lie", "impostor plan", "Admin\"", "location"):
        assert secret not in blob.replace("I was in Admin", "")
    assert evs[0].text == "I was in Admin doing tasks."


def test_amongus_features_do_not_take_labels():
    import inspect
    sig = inspect.signature(amongus.player_features)
    assert list(sig.parameters) == ["events", "upto_step"]
