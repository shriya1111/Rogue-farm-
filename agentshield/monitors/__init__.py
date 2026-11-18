from .baseline import BaselineMonitor
from .shield import AgentShieldMonitor, ShieldConfig
from .reviewer import HeuristicReviewer, LLMReviewer


class NoMonitor:
    """Reference: never intervenes. Used to measure how much damage the rogue does unchecked."""
    name = "no_monitor"

    def reset(self, agent_ids):
        pass

    def on_dispute(self, transcript, current):
        from ..game import Decision
        return Decision(current.round, "ALLOW", reasons=["No monitor."])

    def after_round(self, transcript):
        from ..game import Decision
        return Decision(transcript[-1].round, "ALLOW", reasons=["No monitor."])


def make_monitor(name: str, reviewer=None):
    if name == "baseline":
        return BaselineMonitor()
    if name == "agentshield":
        return AgentShieldMonitor(reviewer=reviewer)
    if name == "agentshield_noverify":
        return AgentShieldMonitor(ShieldConfig(use_verify=False), reviewer=reviewer, name="agentshield_noverify")
    if name == "no_monitor":
        return NoMonitor()
    raise ValueError(name)


VERIFY_BUDGET = {"baseline": 0, "agentshield": 4, "agentshield_noverify": 0, "no_monitor": 0}
