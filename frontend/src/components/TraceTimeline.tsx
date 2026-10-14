import { useEffect, useRef, useState } from "react";
import type { Step } from "../types";

type Props = { steps: Step[]; selected: string | null; totalMs: number; onCite: (cid: string) => void };

function cell(v: unknown): string {
  if (v === null || v === undefined) return "";
  if (typeof v === "number") return Number.isInteger(v) ? v.toLocaleString() : String(Math.round(v * 1000) / 1000);
  if (typeof v === "object") return JSON.stringify(v);
  return String(v);
}

function Table({ rows, onCite }: { rows: Record<string, unknown>[]; onCite?: (cid: string) => void }) {
  if (!rows.length) return null;
  const cols = Array.from(new Set(rows.flatMap((r) => Object.keys(r))));
  return (
    <div className="table-wrap">
      <table>
        <thead>
          <tr>{cols.map((c) => <th key={c}>{c}</th>)}</tr>
        </thead>
        <tbody>
          {rows.map((r, i) => (
            <tr key={i}>
              {cols.map((c) => {
                const v = cell(r[c]);
                if (c === "evidence" && onCite && /^C\d+$/.test(v))
                  return (
                    <td key={c}>
                      <button className="cite" onClick={() => onCite(v)}>{v}</button>
                    </td>
                  );
                return <td key={c}>{v}</td>;
              })}
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}

function StepCard({ s, idx, open, setOpen, totalMs, onCite, innerRef }: {
  s: Step; idx: number; open: boolean; setOpen: (o: boolean) => void; totalMs: number;
  onCite: (c: string) => void; innerRef?: React.Ref<HTMLDivElement>;
}) {
  const left = totalMs ? (s.start_ms / totalMs) * 100 : 0;
  const width = totalMs ? Math.max((s.ms / totalMs) * 100, 0.8) : 0;
  return (
    <div className={`step step-${s.status} ${open ? "step-open" : ""}`} ref={innerRef}>
      <button className="step-head" onClick={() => setOpen(!open)}>
        <span className="step-idx">{idx + 1}</span>
        <span className="step-agent">{s.agent}</span>
        <span className="step-title">{s.title}</span>
        <span className={`badge badge-${s.status}`}>{s.status}</span>
        <span className="step-ms">{s.status === "skipped" ? "" : `${s.ms} ms`}</span>
        <span className="chev">{open ? "▾" : "▸"}</span>
      </button>
      <div className="timebar"><div style={{ marginLeft: `${left}%`, width: `${width}%` }} /></div>
      {open && (
        <div className="step-body">
          <div className="why"><span className="label">Why</span> {s.reason || "-"}</div>
          {s.summary && <div className="what"><span className="label">Result</span> {s.summary}</div>}
          {s.notes.length > 0 && (
            <ul className="notes">{s.notes.map((n, i) => <li key={i}>{n}</li>)}</ul>
          )}
          {s.items.length > 0 && <Table rows={s.items as Record<string, unknown>[]} onCite={onCite} />}
          {s.queries.map((q, i) => (
            <details key={i} className="query" open={s.queries.length === 1 && q.lang !== "llm"}>
              <summary>
                <span className={`lang lang-${q.lang}`}>{q.lang.toUpperCase()}</span>
                <span className="qlabel">{q.label || "Query"}</span>
                <span className="muted">{q.rows} row{q.rows === 1 ? "" : "s"} · {q.ms} ms</span>
              </summary>
              <pre className="code">{q.text}</pre>
              {Object.keys(q.params || {}).length > 0 && (
                <pre className="code params">{JSON.stringify(q.params, null, 2)}</pre>
              )}
              {q.sample?.length > 0 && (
                <>
                  <div className="label small">First rows returned</div>
                  <Table rows={q.sample} />
                </>
              )}
            </details>
          ))}
          {typeof s.data?.traceback === "string" && <pre className="code err">{s.data.traceback as string}</pre>}
        </div>
      )}
    </div>
  );
}

export function TraceTimeline({ steps, selected, totalMs, onCite }: Props) {
  const [open, setOpen] = useState<Record<number, boolean>>({});
  const refs = useRef<Record<string, HTMLDivElement | null>>({});
  // the Router step explains why the path was taken, so it starts open
  useEffect(() => {
    const r = steps.findIndex((s) => s.agent === "Router");
    setOpen(r >= 0 ? { [r]: true } : {});
  }, [steps]);
  useEffect(() => {
    if (!selected) return;
    const i = steps.findIndex((s) => s.agent === selected);
    if (i >= 0) {
      setOpen((o) => ({ ...o, [i]: true }));
      setTimeout(() => refs.current[selected]?.scrollIntoView({ behavior: "smooth", block: "start" }), 50);
    }
  }, [selected, steps]);
  const allOpen = steps.length > 0 && steps.every((_, i) => open[i]);
  return (
    <div className="card">
      <div className="card-head">
        <h3>Trace</h3>
        <button className="link" onClick={() => setOpen(Object.fromEntries(steps.map((_, i) => [i, !allOpen])))}>
          {allOpen ? "Collapse all" : "Expand all"}
        </button>
      </div>
      {steps.map((s, i) => (
        <StepCard
          key={i}
          s={s}
          idx={i}
          open={!!open[i]}
          setOpen={(o) => setOpen((st) => ({ ...st, [i]: o }))}
          totalMs={totalMs}
          onCite={onCite}
          innerRef={(el) => { refs.current[s.agent] = el; }}
        />
      ))}
    </div>
  );
}
