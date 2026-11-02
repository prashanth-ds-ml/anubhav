import { CheckCircle2, AlertTriangle, XCircle } from "lucide-react";
import { AGENT_STYLE, label } from "../agents";

export function AgentTag({ id }: { id: string }) {
  const s = AGENT_STYLE[id] ?? AGENT_STYLE.code;
  const Icon = s.icon;
  return (
    <span className="tag" style={{ color: s.color, borderColor: s.color }}>
      <Icon size={14} aria-hidden /> {id === "code" ? "Safety checks (code)" : label(id)}
    </span>
  );
}

export function Verdict({ v }: { v: "pass" | "warn" | "fail" }) {
  const map = {
    pass: { Icon: CheckCircle2, text: "Validated", cls: "ok" },
    warn: { Icon: AlertTriangle, text: "Warning", cls: "warn" },
    fail: { Icon: XCircle, text: "Rejected", cls: "err" },
  }[v];
  return (
    <span className={`pill ${map.cls}`}>
      <map.Icon size={14} aria-hidden /> {map.text}
    </span>
  );
}
