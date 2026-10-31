"""The agent roster as data (configs/agents.yaml): who exists, what each is for, its instructions and limits.
Adding an agent is adding a spec; nothing here knows about a particular business."""

from dataclasses import dataclass, field
from pathlib import Path

import yaml

from ..agent.graph import Limits
from ..data.config import ROOT

PATH = ROOT / "configs" / "agents.yaml"


@dataclass(frozen=True)
class AgentSpec:
    agent_id: str
    name: str
    purpose: str
    instructions: str
    model: str = "open"
    status: str = "active"
    voice: bool = False
    limits: Limits = field(default_factory=Limits)
    handles: tuple = ()

    @property
    def active(self):
        return self.status == "active"


@dataclass(frozen=True)
class Roster:
    agents: dict
    max_depth: int = 2
    team_max_usd: float = 0.40

    def get(self, agent_id):
        return self.agents.get(agent_id)

    def active(self):
        return [a for a in self.agents.values() if a.active]

    def handler(self, event, exclude=""):
        """The active agent that takes this kind of event (e.g. tool_missing), if any."""
        return next((a for a in self.active() if event in a.handles and a.agent_id != exclude), None)

    def lead(self):
        """The agent that talks to the person (exactly one has voice)."""
        return next(a for a in self.agents.values() if a.voice)


def load(path: Path = PATH) -> Roster:
    cfg = yaml.safe_load(Path(path).read_text(encoding="utf-8"))
    agents = {aid: AgentSpec(aid, a["name"], a["purpose"].strip(), a["instructions"].strip(), a.get("model", "open"),
                             a.get("status", "active"), bool(a.get("voice")), Limits(**a.get("limits", {})), tuple(a.get("handles", ())))
              for aid, a in cfg["agents"].items()}
    if sum(a.voice for a in agents.values()) != 1:
        raise ValueError("exactly one agent must talk to the person (voice: true)")
    d = cfg.get("delegation", {})
    return Roster(agents, d.get("max_depth", 2), d.get("team_max_usd", 0.40))
