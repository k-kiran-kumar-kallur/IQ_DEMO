import { useCallback, useEffect, useMemo, useState } from "react";
import { api, setUnauthorizedHandler } from "./api";
import { AgentPath } from "./components/AgentPath";
import { AnswerText } from "./components/AnswerText";
import { GraphView } from "./components/GraphView";
import { Login } from "./components/Login";
import { SettingsDialog } from "./components/SettingsDialog";
import { Sources } from "./components/Sources";
import { TraceTimeline } from "./components/TraceTimeline";
import type { HistoryRow, Me, Result, Status } from "./types";

const VERIFY_LABEL: Record<string, string> = {
  verified: "Verified: every figure found in the evidence",
  "partially verified": "Partially verified: some figures not found in the evidence",
  "no citations": "No citations in the answer",
  "citation error": "Answer cites evidence that does not exist",
  "not checked": "Not checked",
  "no evidence": "No evidence available to you",
};

export default function App() {
  // undefined while the session check is running, null when signed out
  const [me, setMe] = useState<Me | null | undefined>(undefined);
  const [status, setStatus] = useState<Status | null>(null);
  const [samples, setSamples] = useState<string[]>([]);
  const [history, setHistory] = useState<HistoryRow[]>([]);
  const [question, setQuestion] = useState("");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  const [result, setResult] = useState<Result | null>(null);
  const [focus, setFocus] = useState<string | null>(null);
  const [selected, setSelected] = useState<string | null>(null);
  const [showSettings, setShowSettings] = useState(false);

  useEffect(() => {
    setUnauthorizedHandler(() => setMe(null));
    api.me().then(setMe).catch(() => setMe(null));
  }, []);

  const refresh = useCallback(() => {
    api.status().then(setStatus).catch(() => setStatus(null));
    api.history().then(setHistory).catch(() => undefined);
  }, []);

  const openHistory = useCallback(async (id: number) => {
    window.history.replaceState(null, "", `?id=${id}`);
    const r = await api.historyItem(id);
    setResult(r);
    setQuestion(r.question);
    setFocus(null);
    setSelected(null);
  }, []);

  useEffect(() => {
    if (!me) return;
    refresh();
    api.samples().then(setSamples).catch(() => undefined);
    // deep links: ?id=<history id> opens one of your saved answers with its full trace
    const id = new URLSearchParams(window.location.search).get("id");
    if (id) openHistory(Number(id)).catch(() => window.history.replaceState(null, "", "/"));
  }, [me, refresh, openHistory]);

  const signOut = async () => {
    await api.logout().catch(() => undefined);
    setMe(null);
  };

  // everything shown belongs to the signed-in user, so clear it when the user changes
  useEffect(() => {
    if (me === null) {
      setResult(null);
      setHistory([]);
      setQuestion("");
      setError("");
      setStatus(null);
      setShowSettings(false);
    }
  }, [me]);

  const ask = async (q = question) => {
    if (!q.trim()) return;
    setBusy(true);
    setError("");
    setFocus(null);
    setSelected(null);
    try {
      const r = await api.ask(q);
      setResult(r);
      window.history.replaceState(null, "", `?id=${r.id}`);
      refresh();
    } catch (e) {
      setError(e instanceof Error ? e.message : String(e));
    } finally {
      setBusy(false);
    }
  };

  const cite = (cid: string) => {
    setFocus(null);
    setTimeout(() => setFocus(cid), 0);
  };

  const validCids = useMemo(() => new Set(result?.evidence.map((e) => e.cid) || []), [result]);
  const ready = status?.neo4j.ok && (status?.neo4j.chunks || 0) > 0;

  if (me === undefined) return <div className="app"><p className="muted center">Checking your session…</p></div>;
  if (me === null) return <Login onLogin={setMe} />;

  const grants = Object.entries(me.grants);

  return (
    <div className="app">
      <header>
        <div className="brand">
          <span className="logo">IQ</span>
          <div>
            <div className="brand-name">Enterprise IQ · Ask</div>
            <div className="muted small">Questions answered from SharePoint documents, trackers and the knowledge graph</div>
          </div>
        </div>
        <div className="chips">
          <span className={`chip ${status?.neo4j.ok ? "ok" : "bad"}`} title={status?.neo4j.error || ""}>
            Neo4j {status?.neo4j.ok
              ? `· ${status.neo4j.server?.version || ""} · ${(status.neo4j.docs || 0)} docs · ${(status.neo4j.chunks || 0).toLocaleString()} chunks`
              : "· not connected"}
          </span>
          <span className={`chip ${status?.llm.configured ? "ok" : "warn"}`}>
            Model · {status?.llm.provider === "gemini" ? status.llm.model : "evidence only"}
          </span>
          <span className="chip">Embeddings · {status?.embed_model?.split("/").pop()}</span>
          {me.is_admin && <button onClick={() => setShowSettings(true)}>Settings</button>}
          <span className="chip user" title={me.title}>{me.display_name} · {me.role_name}</span>
          <button onClick={signOut}>Sign out</button>
        </div>
      </header>

      <div className="layout">
        <aside>
          <div className="card">
            <h3>Your access</h3>
            <div className="who">
              <b>{me.display_name}</b> <span className="muted small">({me.username})</span>
              <div className="muted small">{me.title} · {me.role_name}</div>
            </div>
            <p className="muted small">{me.note}</p>
            <ul className="grants">
              {grants.map(([iq, lvl]) => (
                <li key={iq}><span>{iq}</span><b className={`lvl lvl-${lvl}`}>{lvl}</b></li>
              ))}
              {grants.length === 0 && <li className="muted">No IQ access{me.is_admin ? " (admin manages settings only)" : ""}</li>}
            </ul>
            {me.account_names.length > 0 && (
              <div className="scope">
                <span className="label small">Your accounts</span>
                {me.account_names.map((a, i) => <span key={a} className="ent" title={me.accounts[i]}>{a}</span>)}
              </div>
            )}
            {me.partner_names.length > 0 && (
              <div className="scope">
                <span className="label small">Your partners</span>
                {me.partner_names.map((p, i) => <span key={p} className="ent" title={me.partners[i]}>{p}</span>)}
              </div>
            )}
          </div>
          <div className="card">
            <h3>Try these</h3>
            <ul className="list">
              {samples.map((s) => (
                <li key={s}>
                  <button className="link left" onClick={() => { setQuestion(s); ask(s); }}>{s}</button>
                </li>
              ))}
            </ul>
          </div>
          <div className="card">
            <h3>Your history</h3>
            {history.length === 0 && <p className="muted small">No questions yet.</p>}
            <ul className="list">
              {history.map((h) => (
                <li key={h.id}>
                  <button className="link left" onClick={() => openHistory(h.id)}>
                    {h.question}
                    <span className="muted small"> · {h.status} · {h.total_ms} ms</span>
                  </button>
                </li>
              ))}
            </ul>
          </div>
        </aside>

        <main>
          {status && !ready && (
            <div className="card notice">
              {!status.neo4j.ok ? (
                <>
                  <b>Neo4j is not connected.</b>{" "}
                  {me.is_admin ? (
                    <>
                      Add <code>NEO4J_URI</code>, <code>NEO4J_USERNAME</code> and <code>NEO4J_PASSWORD</code> to{" "}
                      <code>IQ/.env</code> (then restart the backend), or enter them in{" "}
                      <button className="link" onClick={() => setShowSettings(true)}>Settings</button>.
                    </>
                  ) : "Ask a platform admin to configure the connection."}
                  {status.neo4j.error && <div className="muted small">{status.neo4j.error}</div>}
                </>
              ) : (
                <>
                  <b>Neo4j is connected but empty.</b>{" "}
                  {me.is_admin ? (
                    <>Open <button className="link" onClick={() => setShowSettings(true)}>Settings</button> and click <i>Load test documents</i>.</>
                  ) : "Ask a platform admin to load the documents."}
                </>
              )}
            </div>
          )}

          <div className="card askbox">
            <textarea
              value={question}
              onChange={(e) => setQuestion(e.target.value)}
              onKeyDown={(e) => { if (e.key === "Enter" && (e.metaKey || e.ctrlKey)) ask(); }}
              placeholder="Ask about accounts, deals, bids, campaigns, partners or delivery… (Cmd+Enter to ask)"
              rows={3}
            />
            <div className="row">
              <span className="muted small">Answers use only what <b>{me.display_name}</b> ({me.role_name}) may see</span>
              <button className="primary" disabled={busy || !question.trim()} onClick={() => ask()}>
                {busy ? "Running agents…" : "Ask"}
              </button>
            </div>
            {error && <div className="error">{error}</div>}
          </div>

          {busy && <div className="card muted">Running permissions → entity resolver → router → graph, document and facts agents → composer → verifier…</div>}

          {result && !busy && (
            <>
              <div className="card answer">
                <div className="q">{result.question}</div>
                <div className="meta muted small">
                  Asked by {result.user_name} · {new Date(result.asked_at).toLocaleString()} · {result.total_ms.toLocaleString()} ms ·{" "}
                  {result.llm?.provider} {result.llm?.model && result.llm.model !== "-" ? `· ${result.llm.model}` : ""}
                  {result.llm?.input_tokens ? ` · ${result.llm.input_tokens.toLocaleString()} in / ${result.llm.output_tokens?.toLocaleString()} out tokens` : ""}
                </div>
                <AnswerText text={result.answer} onCite={cite} validCids={validCids} />
                <div className={`verify v-${result.status.replace(/\s/g, "-")}`}>
                  {VERIFY_LABEL[result.status] || result.status}
                  {result.verification?.numbers_checked ? ` (${result.verification.numbers_checked - result.verification.unsupported.length}/${result.verification.numbers_checked} figures)` : ""}
                  {result.verification?.unsupported?.length ? ` · not found: ${result.verification.unsupported.join(", ")}` : ""}
                </div>
                {result.entities.length > 0 && (
                  <div className="entities">
                    <span className="label small">Understood as</span>
                    {result.entities.map((e) => <span key={e.id} className="ent">{e.label} · {e.id} · {e.name}</span>)}
                  </div>
                )}
              </div>

              <AgentPath path={result.path} selected={selected} onSelect={setSelected} totalMs={result.total_ms} />

              <div className="cols">
                <div className="col">
                  <Sources evidence={result.evidence} cited={result.verification?.cited || []} focus={focus} />
                  {result.subgraph?.nodes && result.subgraph.nodes.length > 0 && (
                    <GraphView nodes={result.subgraph.nodes} edges={result.subgraph.edges || []} paths={result.subgraph.paths || []} />
                  )}
                </div>
                <div className="col">
                  <TraceTimeline steps={result.steps} selected={selected} totalMs={result.total_ms} onCite={cite} />
                </div>
              </div>
            </>
          )}
        </main>
      </div>
      {showSettings && me.is_admin && <SettingsDialog onClose={() => setShowSettings(false)} onChanged={refresh} />}
    </div>
  );
}
