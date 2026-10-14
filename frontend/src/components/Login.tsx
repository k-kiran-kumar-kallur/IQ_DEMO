import { useEffect, useState } from "react";
import { api } from "../api";
import type { DemoUser, Me } from "../types";

type Props = { onLogin: (me: Me) => void };

/** Sign-in page. Lists the demo users so testers can see who can see what; passwords are checked against the
 *  salted hashes stored in SQLite. */
export function Login({ onLogin }: Props) {
  const [username, setUsername] = useState("");
  const [password, setPassword] = useState("");
  const [error, setError] = useState("");
  const [busy, setBusy] = useState(false);
  const [demo, setDemo] = useState<{ users: DemoUser[]; password_hint: string } | null>(null);

  useEffect(() => {
    api.demoUsers().then(setDemo).catch(() => undefined);
  }, []);

  const submit = async (e?: React.FormEvent) => {
    e?.preventDefault();
    setBusy(true);
    setError("");
    try {
      onLogin(await api.login(username, password));
    } catch (ex) {
      setError(ex instanceof Error ? ex.message : String(ex));
    } finally {
      setBusy(false);
    }
  };

  const scope = (u: DemoUser) => {
    if (u.partner_names.length) return `Partners: ${u.partner_names.join(", ")}`;
    if (u.account_names.length) return `Accounts: ${u.account_names.join(", ")}`;
    return "";
  };

  return (
    <div className="login-page">
      <div className="login-card card">
        <div className="brand">
          <span className="logo">IQ</span>
          <div>
            <div className="brand-name">Enterprise IQ · Ask</div>
            <div className="muted small">Sign in to ask questions. You only see what your role allows.</div>
          </div>
        </div>
        <form onSubmit={submit} className="login-form">
          <label className="field">
            <span>Username</span>
            <input value={username} autoFocus autoComplete="username" onChange={(e) => setUsername(e.target.value)} />
          </label>
          <label className="field">
            <span>Password</span>
            <input type="password" value={password} autoComplete="current-password"
                   onChange={(e) => setPassword(e.target.value)} />
          </label>
          {error && <div className="error">{error}</div>}
          <button className="primary wide" disabled={busy || !username || !password}>{busy ? "Signing in…" : "Sign in"}</button>
        </form>
      </div>

      {demo && (
        <div className="card demo-users">
          <div className="card-head">
            <h3>Demo users</h3>
            <span className="muted small">{demo.password_hint}. Click a row to fill the username.</span>
          </div>
          <div className="table-wrap">
            <table>
              <thead>
                <tr><th>User</th><th>Role</th><th>What they can see</th></tr>
              </thead>
              <tbody>
                {demo.users.map((u) => (
                  <tr key={u.username} className={`pick ${username === u.username ? "picked" : ""}`}
                      onClick={() => { setUsername(u.username); setPassword(""); setError(""); }}>
                    <td><b>{u.display_name}</b><div className="muted small">{u.username}</div></td>
                    <td>{u.role_name}<div className="muted small">{u.title}</div></td>
                    <td>{u.note}{scope(u) && <div className="muted small">{scope(u)}</div>}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </div>
      )}
    </div>
  );
}
