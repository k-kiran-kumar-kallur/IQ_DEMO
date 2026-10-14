import { useEffect, useRef, useState } from "react";
import { api } from "../api";
import type { Evidence } from "../types";

type Props = { evidence: Evidence[]; cited: string[]; focus: string | null };

const KIND: Record<string, string> = { document: "Document passage", graph: "Graph walk", fact: "SQL fact table" };

function Card({ e, cited, focused, innerRef }: { e: Evidence; cited: boolean; focused: boolean; innerRef: (el: HTMLDivElement | null) => void }) {
  const [expanded, setExpanded] = useState(false);
  useEffect(() => { if (focused) setExpanded(true); }, [focused]);
  const preview = expanded ? e.text : e.text.split("\n").slice(0, 4).join("\n");
  return (
    <div className={`ev ev-${e.kind} ${focused ? "ev-focus" : ""} ${cited ? "" : "ev-unused"}`} ref={innerRef}>
      <div className="ev-head">
        <span className="cite static">{e.cid}</span>
        <span className={`kind kind-${e.kind}`}>{KIND[e.kind]}</span>
        <span className="iq">{e.iq} IQ</span>
        {e.classification && <span className={`cls cls-${e.classification.toLowerCase()}`}>{e.classification}</span>}
        {!cited && <span className="muted small">not cited in answer</span>}
      </div>
      <div className="ev-title">
        {e.title}
        {e.section ? <span className="muted"> · {e.section}</span> : null}
      </div>
      <div className="ev-src">
        {e.kind === "document" && e.raw_path ? (
          <a href={api.fileUrl(e.raw_path)} target="_blank" rel="noreferrer">{e.source_path}</a>
        ) : (
          <span>{e.source_path}{e.sheet && e.sheet !== "csv" ? ` › sheet "${e.sheet}"` : ""}</span>
        )}
        {e.sources && e.sources.length > 1 && <span className="muted"> (+{e.sources.length - 1} more source files)</span>}
      </div>
      <div className="ev-why">
        <span className="label">Why selected</span>
        <ul>{e.why.map((w, i) => <li key={i}>{w}</li>)}</ul>
      </div>
      <pre className="ev-text">{preview}</pre>
      {e.text.split("\n").length > 4 && (
        <button className="link" onClick={() => setExpanded(!expanded)}>{expanded ? "Show less" : "Show full evidence"}</button>
      )}
      {e.sql && expanded && <pre className="code">{e.sql}</pre>}
    </div>
  );
}

export function Sources({ evidence, cited, focus }: Props) {
  const refs = useRef<Record<string, HTMLDivElement | null>>({});
  useEffect(() => {
    if (focus) refs.current[focus]?.scrollIntoView({ behavior: "smooth", block: "center" });
  }, [focus]);
  const citedSet = new Set(cited);
  const docs = new Set(evidence.filter((e) => e.kind === "document").map((e) => e.source_path));
  return (
    <div className="card">
      <div className="card-head">
        <h3>Sources</h3>
        <span className="muted">
          {evidence.length} evidence item{evidence.length === 1 ? "" : "s"} · {docs.size} document{docs.size === 1 ? "" : "s"} ·{" "}
          {cited.length} cited
        </span>
      </div>
      {evidence.length === 0 && <p className="muted">Nothing was retrieved.</p>}
      {evidence.map((e) => (
        <Card key={e.cid} e={e} cited={citedSet.has(e.cid)} focused={focus === e.cid}
              innerRef={(el) => { refs.current[e.cid] = el; }} />
      ))}
    </div>
  );
}
