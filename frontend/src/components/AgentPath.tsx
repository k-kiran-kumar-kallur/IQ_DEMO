import type { PathNode } from "../types";

type Props = { path: PathNode[]; selected: string | null; onSelect: (agent: string) => void; totalMs: number };

const ICON: Record<string, string> = { ran: "✓", skipped: "–", error: "!" };

function Node({ n, selected, onSelect }: { n?: PathNode; selected: boolean; onSelect: (a: string) => void }) {
  if (!n) return null;
  return (
    <button
      className={`pnode pnode-${n.status} ${selected ? "pnode-sel" : ""}`}
      onClick={() => onSelect(n.agent)}
      title={`${n.agent}: ${n.reason}`}
    >
      <div className="pnode-head">
        <span className={`dot dot-${n.status}`}>{ICON[n.status] || "?"}</span>
        <span className="pnode-name">{n.agent}</span>
        <span className="pnode-ms">{n.status === "skipped" ? "skipped" : `${n.ms} ms`}</span>
      </div>
      <div className="pnode-sum">{n.status === "skipped" ? n.reason : n.summary}</div>
    </button>
  );
}

/** The route the question took: three set-up agents, three retrieval agents side by side, then compose and verify. */
export function AgentPath({ path, selected, onSelect, totalMs }: Props) {
  const by = (a: string) => path.find((p) => p.agent === a);
  const arrow = <div className="parrow" aria-hidden>→</div>;
  return (
    <div className="card">
      <div className="card-head">
        <h3>Agent path</h3>
        <span className="muted">
          {totalMs.toLocaleString()} ms end to end · click an agent to see what it did and why
        </span>
      </div>
      <div className="path">
        <Node n={by("Permissions")} selected={selected === "Permissions"} onSelect={onSelect} />
        {arrow}
        <Node n={by("Entity resolver")} selected={selected === "Entity resolver"} onSelect={onSelect} />
        {arrow}
        <Node n={by("Router")} selected={selected === "Router"} onSelect={onSelect} />
        {arrow}
        <div className="branch">
          {["Graph agent", "Document agent", "Facts agent"].map((a) => (
            <Node key={a} n={by(a)} selected={selected === a} onSelect={onSelect} />
          ))}
        </div>
        {arrow}
        <Node n={by("Composer")} selected={selected === "Composer"} onSelect={onSelect} />
        {arrow}
        <Node n={by("Verifier")} selected={selected === "Verifier"} onSelect={onSelect} />
      </div>
    </div>
  );
}
