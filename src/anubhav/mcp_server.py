"""MCP server for one authenticated company session. Only the tools that session's role may use are registered,
so tools/list differs by authorization (as the MCP spec allows); every call goes through the broker.

  uv run python -m anubhav.mcp_server --company T01 --role dispatcher        # stdio, e.g. for an MCP client
"""

import argparse
import inspect
from pathlib import Path

from mcp.server.mcpserver import MCPServer
from mcp.server.mcpserver.exceptions import ToolError as MCPToolError

from .data.config import ROOT
from .learning import newtools
from .learning.store import LessonStore
from .runtime.broker import Broker, Session
from .runtime.company import CompanyData

DEFAULT_WORLD = ROOT / "data" / "worlds" / "full_seed20261104"


def _bind(broker, tool):
    def fn(**kwargs):
        out = broker.call(tool.name, {k: v for k, v in kwargs.items() if v is not None})
        if not out["ok"]:      # tool execution errors go back as isError results the model can read and correct
            raise MCPToolError(f"{out['error']['code']}: {out['error']['message']}")
        return out["result"]
    params, ann = [], {}
    for name, f in tool.args.model_fields.items():
        default = inspect.Parameter.empty if f.is_required() else f.default
        params.append(inspect.Parameter(name, inspect.Parameter.KEYWORD_ONLY, default=default, annotation=f.annotation))
        ann[name] = f.annotation
    fn.__signature__ = inspect.Signature(params, return_annotation=dict)
    fn.__annotations__ = {**ann, "return": dict}
    fn.__name__ = tool.name
    return fn


def build_server(broker: Broker) -> MCPServer:
    s = broker.s
    server = MCPServer(name=f"anubhav-{s.company}", version="0.1.0",
                       instructions=f"Logistics tools for company {s.company} (role: {s.role}). Drafts only; nothing is dispatched.")
    for tool in broker.list_tools():
        server.add_tool(_bind(broker, tool), name=tool.name, description=tool.description)
    return server


def learned_for(world, company):
    """The tools a person approved for this company: the server offers them like any other tool."""
    path = Path(world) / "learning" / "demo.sqlite"
    return newtools.tools(LessonStore(path), company, "active") if path.exists() else []


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument("--company", required=True)
    ap.add_argument("--role", default="dispatcher")
    ap.add_argument("--user", default="planner")
    ap.add_argument("--world", default=str(DEFAULT_WORLD))
    a = ap.parse_args(argv)
    broker = Broker(CompanyData(Path(a.world), a.company), Session(a.company, a.role, a.user),
                    learned_tools=learned_for(a.world, a.company))
    build_server(broker).run()


if __name__ == "__main__":
    main()
