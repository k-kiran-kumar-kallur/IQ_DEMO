import { useEffect, useState } from "react";
import { api } from "../api";
import type { IngestState, LoginAudit, Me, SettingField } from "../types";

type Props = { onClose: () => void; onChanged: () => void };

const GROUPS: { title: string; hint: string; keys: [string, string][] }[] = [
  {
    title: "Neo4j Aura",
    hint: "Read from NEO4J_* in IQ/.env. Anything typed here overrides .env and is stored in data/iq.db.",
    keys: [["neo4j_uri", "Connection URI"], ["neo4j_username", "Username"], ["neo4j_password", "Password"],
           ["neo4j_database", "Database (blank = default)"]],
  },
  {
    title: "Answer model",
    hint: "Gemini via its OpenAI-compatible API, from GOOGLE_API_KEY / GEMINI_* in .env. 'none' builds answers straight from the evidence.",
    keys: [["llm_provider", "Provider"], ["gemini_chat_model", "Chat model"], ["gemini_api_key", "API key"],
           ["gemini_base_url", "Base URL"]],
  },
  {
    title: "Embeddings",
    hint: "Runs locally with fastembed. Changing the model needs a fresh load of the documents.",
    keys: [["embed_model", "Embedding model"]],
  },
];

export function SettingsDialog({ onClose, onChanged }: Props) {
  const [fields, setFields] = useState<Record<string, SettingField>>({});
  const [values, setValues] = useState<Record<string, string>>({});
  const [msg, setMsg] = useState<string>("");
  const [test, setTest] = useState<string>("");
  const [ingest, setIngest] = useState<IngestState | null>(null);
  const [reset, setReset] = useState(true);
  const [users, setUsers] = useState<Me[]>([]);
  const [audit, setAudit] = useState<LoginAudit[]>([]);

  useEffect(() => {
    api.settings().then((f) => {
      setFields(f);
      setValues(Object.fromEntries(Object.entries(f).map(([k, v]) => [k, v.secret ? "" : v.value])));
    });
    api.ingestStatus().then(setIngest).catch(() => undefined);
    api.users().then(setUsers).catch(() => undefined);
    api.loginAudit().then(setAudit).catch(() => undefined);
  }, []);

  useEffect(() => {
    if (!ingest?.running) return;
    const t = setInterval(() => api.ingestStatus().then((s) => {
      setIngest(s);
      if (!s.running) onChanged();
    }), 1000);
    return () => clearInterval(t);
  }, [ingest?.running, onChanged]);

  const save = async () => {
    setMsg("Saving…");
    try {
      const f = await api.saveSettings(values);
      setFields(f);
      setMsg("Saved.");
      onChanged();
    } catch (e) {
      setMsg(String(e));
    }
  };
  const testConn = async () => {
    setTest("Testing…");
    await api.saveSettings(values);
    const r = await api.testNeo4j();
    setTest(r.ok ? `Connected in ${r.ms} ms · ${r.nodes?.toLocaleString()} nodes in the database` : `Failed: ${r.error}`);
    onChanged();
  };
  const startIngest = async () => {
    try {
      setIngest(await api.ingest(reset));
    } catch (e) {
      setMsg(String(e));
    }
  };

  const pct = ingest && ingest.total ? Math.round((ingest.done / ingest.total) * 100) : 0;

  return (
    <div className="modal-bg" onClick={onClose}>
      <div className="modal" onClick={(e) => e.stopPropagation()}>
        <div className="card-head">
          <h2>Settings</h2>
          <button className="link" onClick={onClose}>Close</button>
        </div>
        {GROUPS.map((g) => (
          <section key={g.title} className="sgroup">
            <h3>{g.title}</h3>
            <p className="muted small">{g.hint}</p>
            {g.keys.map(([k, label]) => {
              const f = fields[k];
              if (!f) return null;
              return (
                <label key={k} className="field">
                  <span>{label} <em className="muted small">({f.env} · from {f.source})</em></span>
                  {k === "llm_provider" ? (
                    <select value={values[k] || "gemini"} onChange={(e) => setValues({ ...values, [k]: e.target.value })}>
                      <option value="gemini">gemini</option>
                      <option value="none">none (evidence only)</option>
                    </select>
                  ) : (
                    <input
                      type={f.secret ? "password" : "text"}
                      value={values[k] ?? ""}
                      placeholder={f.secret ? (f.is_set ? "•••••••• (set; leave blank to keep)" : "not set") : ""}
                      onChange={(e) => setValues({ ...values, [k]: e.target.value })}
                    />
                  )}
                </label>
              );
            })}
          </section>
        ))}
        <div className="row">
          <button className="primary" onClick={save}>Save</button>
          <button onClick={testConn}>Test Neo4j connection</button>
          <span className="muted small">{msg} {test}</span>
        </div>

        <section className="sgroup">
          <h3>Load documents</h3>
          <p className="muted small">
            Reads IQ/test_documents (skipping _reference/ and README.md), copies originals to data/raw, loads tables into
            SQLite, builds graph entities, embeds every chunk locally and writes it all to Neo4j.
          </p>
          <div className="row">
            <label className="check">
              <input type="checkbox" checked={reset} onChange={(e) => setReset(e.target.checked)} /> Clear the Neo4j database first
            </label>
            <button className="primary" disabled={!!ingest?.running} onClick={startIngest}>
              {ingest?.running ? "Loading…" : "Load test documents"}
            </button>
          </div>
          {ingest && ingest.phase !== "idle" && (
            <div className="ingest">
              <div className="muted small">{ingest.phase} {ingest.total ? `· ${ingest.done}/${ingest.total}` : ""}</div>
              <div className="progress"><div style={{ width: `${ingest.phase === "done" ? 100 : pct}%` }} /></div>
              <pre className="code log">{ingest.log.join("\n")}</pre>
            </div>
          )}
        </section>

        <section className="sgroup">
          <h3>Users</h3>
          <p className="muted small">
            Stored in the <code>users</code> table of data/iq.db with salted scrypt password hashes. Access comes from the
            role; account owners, GTM, marketing and delivery leads are limited to their own accounts, alliance managers to
            their partners.
          </p>
          <div className="table-wrap">
            <table>
              <thead><tr><th>User</th><th>Role</th><th>Scope</th><th>Last sign-in</th></tr></thead>
              <tbody>
                {users.map((u) => (
                  <tr key={u.username}>
                    <td><b>{u.display_name}</b><div className="muted small">{u.username}{u.active ? "" : " · inactive"}</div></td>
                    <td>{u.role_name}</td>
                    <td>{[...u.account_names, ...u.partner_names].join(", ") ||
                      <span className="muted">{u.is_admin ? "settings only, no business data" : "all within role"}</span>}</td>
                    <td className="muted">{u.last_login ? new Date(u.last_login).toLocaleString() : "never"}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </section>

        <section className="sgroup">
          <h3>Sign-in audit</h3>
          <p className="muted small">Last 50 attempts from the <code>login_audit</code> table. Five wrong passwords lock a user for 10 minutes.</p>
          <div className="table-wrap">
            <table>
              <thead><tr><th>When</th><th>User</th><th>Result</th><th>Reason</th><th>IP</th></tr></thead>
              <tbody>
                {audit.map((a) => (
                  <tr key={a.id}>
                    <td className="muted">{new Date(a.at).toLocaleString()}</td>
                    <td>{a.username}</td>
                    <td className={a.success ? "audit-ok" : "audit-fail"}>{a.success ? "ok" : "failed"}</td>
                    <td>{a.reason}</td>
                    <td className="muted">{a.ip}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </section>
      </div>
    </div>
  );
}
