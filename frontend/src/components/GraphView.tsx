import type { GEdge, GNode } from "../types";

type Props = { nodes: GNode[]; edges: GEdge[]; paths: string[] };

const COLORS: Record<string, string> = {
  Account: "#2563eb", Opportunity: "#0d9488", Bid: "#7c3aed", Contract: "#d97706", Programme: "#db2777", Project: "#e11d48",
  Contact: "#0891b2", Partner: "#65a30d", Campaign: "#9333ea", Funding: "#ca8a04", Registration: "#4b5563",
};

/** Radial drawing of the subgraph the graph agent walked: starting nodes in the centre, connected nodes around them. */
export function GraphView({ nodes, edges, paths }: Props) {
  if (!nodes.length) return null;
  const W = 760, H = 460, cx = W / 2, cy = H / 2;
  const roots = nodes.filter((n) => n.root);
  const others = nodes.filter((n) => !n.root);
  const pos: Record<string, { x: number; y: number }> = {};
  roots.forEach((n, i) => { pos[n.id] = { x: cx + (i - (roots.length - 1) / 2) * 150, y: cy }; });
  const rings = others.length > 22 ? [150, 205] : [175];
  others.forEach((n, i) => {
    const ring = rings.length === 2 ? i % 2 : 0;
    const a = (2 * Math.PI * i) / Math.max(others.length, 1) - Math.PI / 2;
    pos[n.id] = { x: cx + Math.cos(a) * rings[ring] * 1.55, y: cy + Math.sin(a) * rings[ring] };
  });
  const labels = Array.from(new Set(nodes.map((n) => n.label)));
  return (
    <div className="card">
      <div className="card-head">
        <h3>Graph walk</h3>
        <span className="muted">{nodes.length} nodes · {edges.length} relationships · hover a line for its type</span>
      </div>
      <svg viewBox={`0 0 ${W} ${H}`} className="graph" role="img" aria-label="Subgraph walked by the graph agent">
        {edges.map((e, i) => {
          const a = pos[e.source], b = pos[e.target];
          if (!a || !b) return null;
          return (
            <line key={i} x1={a.x} y1={a.y} x2={b.x} y2={b.y} className="gedge">
              <title>{`${e.source} -[${e.type}]-> ${e.target}`}</title>
            </line>
          );
        })}
        {nodes.map((n) => {
          const p = pos[n.id];
          const r = n.root ? 15 : 8;
          const name = (n.name || "").length > 26 ? (n.name || "").slice(0, 25) + "…" : n.name || "";
          return (
            <g key={n.id}>
              <circle cx={p.x} cy={p.y} r={r} fill={COLORS[n.label] || "#64748b"} className={n.root ? "groot" : ""}>
                <title>{`${n.label} ${n.id} ${n.name || ""}`}</title>
              </circle>
              <text x={p.x} y={p.y + r + 12} textAnchor="middle" className="glabel">{n.id}</text>
              <text x={p.x} y={p.y + r + 24} textAnchor="middle" className="gname">{name}</text>
            </g>
          );
        })}
      </svg>
      <div className="legend">
        {labels.map((l) => (
          <span key={l}><i style={{ background: COLORS[l] || "#64748b" }} />{l}</span>
        ))}
      </div>
      <details className="paths">
        <summary>Paths walked ({paths.length})</summary>
        <pre className="code">{paths.join("\n")}</pre>
      </details>
    </div>
  );
}
