"""The agent roster as data (configs/agents.yaml): who exists, what each is for, its instructions and limits.
Adding an agent is adding a spec; nothing here knows about a particular business."""

import re
from dataclasses import dataclass, field
from pathlib import Path

import yaml

from ..agent.graph import Limits
from ..data.config import ROOT

PATH = ROOT / "configs" / "agents.yaml"
SKILLS = ROOT / "configs" / "skills"        # configs/skills/<agent>/<skill>/SKILL.md, like Claude skills
ALWAYS = {"load_skill"}                     # every agent may read its own skills


@dataclass(frozen=True)
class Skill:
    """A method the agent can load when it needs it: a name and a one-line description in its instructions, the full
    text on demand (load_skill). Skills say how to work, never facts about a business (those are lessons)."""
    name: str
    description: str
    path: Path

    def body(self):
        return _split(self.path.read_text(encoding="utf-8"))[1]


def _split(text):
    m = re.match(r"^---\s*\n(.*?)\n---\s*\n(.*)$", text, re.S)
    if not m:
        raise ValueError("a SKILL.md starts with a --- block holding name and description")
    head = yaml.safe_load(m.group(1)) or {}
    return head, m.group(2).strip()


def load_skills(agent_id, root=SKILLS):
    out = []
    for p in sorted((Path(root) / agent_id).glob("*/SKILL.md")):
        head, _ = _split(p.read_text(encoding="utf-8"))
        name, desc = str(head.get("name") or ""), str(head.get("description") or "")
        if not re.fullmatch(r"[a-z][a-z0-9-]{2,39}", name) or name != p.parent.name:
            raise ValueError(f"{p}: the name must match its folder and be 3-40 lowercase letters, digits or -")
        if not desc or len(desc) > 300 or "{" in desc or "}" in desc:
            raise ValueError(f"{p}: one description line, up to 300 characters, no braces")
        out.append(Skill(name, desc, p))
    return tuple(out)


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
    # which tools it may call: tool categories, extra tool names, and kinds of action (read, draft, append).
    # None: every tool its role allows (single-agent runs and the frozen experiments use no list)
    tools: dict | None = None
    skills: tuple = ()

    @property
    def active(self):
        return self.status == "active"

    def permits(self, tool):
        if tool.name in ALWAYS or self.tools is None:
            return True
        t = self.tools
        return tool.action in t.get("actions", ("read",)) and (tool.category in t.get("categories", ()) or tool.name in t.get("names", ()))

    def skill(self, name):
        return next((s for s in self.skills if s.name == name), None)

    def skills_text(self):
        """The list the agent sees in its instructions; the full text comes from load_skill."""
        if not self.skills:
            return ""
        return ("\n\nYour skills (call load_skill with the name before doing that kind of work; each is a method, not a fact):\n"
                + "\n".join(f"- {s.name}: {s.description}" for s in self.skills))


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
    agents = {}
    for aid, a in cfg["agents"].items():
        skills = load_skills(aid, Path(path).parent / "skills")
        spec = AgentSpec(aid, a["name"], a["purpose"].strip(), a["instructions"].strip(), a.get("model", "open"),
                         a.get("status", "active"), bool(a.get("voice")), Limits(**a.get("limits", {})), tuple(a.get("handles", ())),
                         a.get("tools"), skills)
        agents[aid] = spec
    if sum(a.voice for a in agents.values()) != 1:
        raise ValueError("exactly one agent must talk to the person (voice: true)")
    d = cfg.get("delegation", {})
    return Roster(agents, d.get("max_depth", 2), d.get("team_max_usd", 0.40))
