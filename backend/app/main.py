"""FastAPI backend for the Enterprise IQ question-and-answer UI. Every data endpoint requires a signed-in user;
what that user can see is decided by their role and entitlements (permissions.py, users table in SQLite)."""
import json

from fastapi import Depends, FastAPI, HTTPException, Request, Response
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from pydantic import BaseModel

from . import auth, db, graph, ingest
from .agents import orchestrator
from .config import RAW_DIR, SETTINGS
from .permissions import DEMO_USERS, ROLES, context, document_allowed

db.init()
auth.init()
app = FastAPI(title="Enterprise IQ - Ask", version="0.2.0")
app.add_middleware(CORSMiddleware, allow_origins=["http://localhost:5173", "http://127.0.0.1:5173"],
                   allow_credentials=True, allow_methods=["*"], allow_headers=["*"])

SAMPLES = [
    "Why is the Northwind renewal at risk and what should we do?",
    "Which deals are stalled?",
    "What is our competitive win rate and why do we lose bids?",
    "Which campaign sourced the Meridian Bank opportunity?",
    "How much partner funding expires in the next 60 days?",
    "What is the status of Project Atlas and its EAC?",
    "What are the gaps in the Calder Insurance RFP compliance matrix?",
    "Who is the new decision maker at Northwind?",
    "What was Northwind's revenue and margin in 2025 and 2026?",
    "How is Wingtip Fleet Analytics performing?",
]


class LoginBody(BaseModel):
    username: str
    password: str


class AskBody(BaseModel):
    question: str


class SettingsBody(BaseModel):
    values: dict


class IngestBody(BaseModel):
    reset: bool = True


# ------------------------------------------------------------------ auth
@app.post("/api/auth/login")
def login(body: LoginBody, request: Request, response: Response):
    token, user = auth.login(body.username, body.password, request.client.host if request.client else "")
    response.set_cookie(auth.COOKIE, token, httponly=True, samesite="lax", max_age=auth.SESSION_HOURS * 3600, path="/")
    return user


@app.post("/api/auth/logout")
def logout(request: Request, response: Response):
    auth.logout(request.cookies.get(auth.COOKIE))
    response.delete_cookie(auth.COOKIE, path="/")
    return {"ok": True}


@app.get("/api/auth/me")
def me(user: dict = Depends(auth.current_user)):
    return user


@app.get("/api/auth/demo-users")
def demo_users():
    """Shown on the sign-in page of this demo: who exists and what each one can see (never passwords)."""
    rows = {u["username"]: u for u in auth.list_users()}
    out = []
    for username, *_ in DEMO_USERS:
        u = rows.get(username)
        if u and u["active"]:
            out.append(dict(username=u["username"], display_name=u["display_name"], title=u["title"],
                            role_name=u["role_name"], note=u["note"], accounts=u["accounts"], partners=u["partners"],
                            account_names=u["account_names"], partner_names=u["partner_names"]))
    return dict(users=out, password_hint=f"All demo users use the password {auth.DEMO_PASSWORD}")


@app.get("/api/users")
def users(_: dict = Depends(auth.require_admin)):
    return auth.list_users()


@app.get("/api/login-audit")
def login_audit(_: dict = Depends(auth.require_admin)):
    with db.session() as c:
        return [dict(r) for r in c.execute("SELECT * FROM login_audit ORDER BY id DESC LIMIT 50").fetchall()]


# ------------------------------------------------------------------ status and settings
@app.get("/api/status")
def status(_: dict = Depends(auth.current_user)):
    out = {"neo4j": {"ok": False}, "llm": {}, "documents": 0}
    try:
        out["neo4j"] = graph.ping()
        rows = graph.run("MATCH (d:Document) WITH count(d) AS docs MATCH (c:Chunk) RETURN docs, count(c) AS chunks")
        out["neo4j"].update(rows[0] if rows else {})
    except Exception as ex:
        out["neo4j"] = {"ok": False, "error": str(ex)[:300]}
    prov = db.get_setting("llm_provider")
    out["llm"] = {"provider": prov, "model": db.get_setting("gemini_chat_model") if prov == "gemini" else "-",
                  "configured": bool(db.get_setting("gemini_api_key")) if prov == "gemini" else True}
    with db.session() as c:
        out["documents"] = c.execute("SELECT count(*) FROM documents").fetchone()[0]
        out["tables"] = c.execute("SELECT count(*) FROM catalog").fetchone()[0]
        last = c.execute("SELECT * FROM ingest_runs ORDER BY id DESC LIMIT 1").fetchone()
        out["last_ingest"] = dict(last) if last else None
    out["embed_model"] = db.get_setting("embed_model")
    return out


@app.get("/api/settings")
def get_settings(_: dict = Depends(auth.require_admin)):
    res = {}
    for k, (env, default, secret) in SETTINGS.items():
        v = db.get_setting(k)
        res[k] = {"value": "" if secret else v, "is_set": bool(v), "secret": secret, "source": db.settings_source(k),
                  "env": env}
    return res


@app.post("/api/settings")
def save_settings(body: SettingsBody, admin: dict = Depends(auth.require_admin)):
    db.save_settings(body.values)
    graph.reset_driver()
    return get_settings(admin)


@app.post("/api/settings/test-neo4j")
def test_neo4j(_: dict = Depends(auth.require_admin)):
    try:
        graph.reset_driver()
        return graph.ping()
    except Exception as ex:
        return {"ok": False, "error": str(ex)[:400]}


@app.post("/api/ingest")
def start_ingest(body: IngestBody, _: dict = Depends(auth.require_admin)):
    if not ingest.start(reset=body.reset):
        raise HTTPException(409, "An ingestion run is already in progress")
    return ingest.STATE


@app.get("/api/ingest/status")
def ingest_status(_: dict = Depends(auth.require_admin)):
    return ingest.STATE


# ------------------------------------------------------------------ questions
@app.get("/api/samples")
def samples(_: dict = Depends(auth.current_user)):
    return SAMPLES


@app.post("/api/ask")
def ask(body: AskBody, user: dict = Depends(auth.current_user)):
    q = body.question.strip()
    if not q:
        raise HTTPException(400, "Question is empty")
    return orchestrator.ask(q, user)


@app.get("/api/history")
def history(limit: int = 30, user: dict = Depends(auth.current_user)):
    with db.session() as c:
        rows = c.execute("SELECT id, asked_at, user, question, status, total_ms FROM questions WHERE user=? "
                         "ORDER BY id DESC LIMIT ?", (user["username"], limit)).fetchall()
    return [dict(r) for r in rows]


@app.get("/api/history/{qid}")
def history_item(qid: int, user: dict = Depends(auth.current_user)):
    with db.session() as c:
        row = c.execute("SELECT id, user, trace_json FROM questions WHERE id=?", (qid,)).fetchone()
    if not row or row["user"] != user["username"]:
        raise HTTPException(404, "Not found")              # other users' questions are invisible, not forbidden
    data = json.loads(row["trace_json"])
    data["id"] = row["id"]
    return data


@app.get("/api/file")
def get_file(path: str, user: dict = Depends(auth.current_user)):
    """Serve an original document from the local file store, only if the user may see the whole document."""
    full = (RAW_DIR / path).resolve()
    if not str(full).startswith(str(RAW_DIR.resolve())) or not full.is_file():
        raise HTTPException(404, "File not found")
    rows = graph.run("MATCH (d:Document {raw_path: $p}) OPTIONAL MATCH (d)-[:HAS_CHUNK]->(c:Chunk) "
                     "RETURN d.iq AS iq, [x IN collect(c.accounts) | x] AS accs", {"p": path})
    if not rows or rows[0]["iq"] is None:
        raise HTTPException(404, "File not found")
    accounts = sorted({a for lst in rows[0]["accs"] for a in (lst or [])})
    if not document_allowed(context(user), rows[0]["iq"], accounts):
        raise HTTPException(403, "You do not have access to the whole of this document")
    return FileResponse(full, filename=full.name)
