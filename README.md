# Enterprise IQ · Ask

A question-and-answer UI over the test corpus in `test_documents/`. Every answer shows **which documents and records it
came from**, **which agents ran, in what order, and why**, and the exact Cypher, SQL and model calls behind it.

| Part | Technology | Where |
| --- | --- | --- |
| Frontend | React 18 + Vite + TypeScript | `frontend/` (http://localhost:5173) |
| Backend | Python FastAPI | `backend/` (http://127.0.0.1:8010, API docs at `/docs`) |
| Graph + vectors | Neo4j Aura (vector index + full-text index on chunks) | your Aura instance |
| Structured facts, history, settings, users and sessions | SQLite | `data/iq.db` |
| Original files | Local file store (stands in for Azure Blob) | `data/raw/` |
| Embeddings | `BAAI/bge-small-en-v1.5` via fastembed, runs locally (384 dimensions) | `data/models/` |
| Answer model | Gemini through its OpenAI-compatible API | settings in `.env` |

`data/` and `.env` are gitignored.

## 1. Configure `.env` (repo root)

```bash
# Neo4j Aura (from the credentials file you downloaded when the instance was created)
NEO4J_URI=neo4j+s://<instance-id>.databases.neo4j.io
NEO4J_USERNAME=neo4j
NEO4J_PASSWORD=<password>

# Gemini (already present)
GOOGLE_API_KEY=...
GEMINI_CHAT_MODEL=...
GEMINI_BASE_URL=https://generativelanguage.googleapis.com/v1beta/openai/

# SQLite file (absolute, or relative to the IQ folder; default data/iq.db)
SQLITE_PATH=data/iq.db
```

A platform admin can also enter these in the app's **Settings** screen. Values saved there override `.env` and are stored in `data/iq.db`.

**TLS note:** the python.org build of Python on macOS ships without CA certificates, so `neo4j+s://` fails with
"Unable to retrieve routing information" (the debug log shows `CERTIFICATE_VERIFY_FAILED`). The backend therefore connects
with full certificate verification against `certifi`'s CA bundle (`backend/app/graph.py`). Running
`/Applications/Python 3.11/Install Certificates.command` also fixes it machine-wide.

## 2. Run

```bash
# backend (first time: python3 -m venv backend/.venv && backend/.venv/bin/pip install -r backend/requirements.txt)
cd backend && .venv/bin/uvicorn app.main:app --host 127.0.0.1 --port 8010 --reload

# frontend, in a second terminal (first time: npm install)
cd frontend && npm run dev
```

Open http://localhost:5173 and sign in (see section 5). Port 8010 is used because 8000 is taken by another app on this machine; to use a different
port, start uvicorn with `--port N` and run the frontend with `IQ_API=http://127.0.0.1:N npm run dev`.

## 3. Load the documents

Sign in as `admin`, then **Settings → Load test documents.** This reads `test_documents/` (skipping `_reference/` and `README.md`) and:

1. copies each original file into `data/raw/test_documents/<doc-id>/<checksum>/`,
2. loads every Excel sheet and CSV table into SQLite and creates views such as `v_revenue`, `v_pipeline`, `v_bids`,
3. builds graph entities from the structured exports (accounts, opportunities, bids, contracts, programmes, projects,
   partners, contacts, campaigns, funding, registrations) and their relationships,
4. splits every document into chunks, embeds them locally and writes `Document` and `Chunk` nodes with `MENTIONS` links
   to the entities they name.

About 100 files become roughly 1,300 chunks and 200 entities, well inside AuraDB Free limits.

## 4. How a question is answered

| Step | Agent | What it does |
| --- | --- | --- |
| 1 | Permissions | Builds the signed-in user's access from their role: full, own-accounts-only, totals-only or none per IQ |
| 2 | Entity resolver | Maps names and IDs in the question ("Northwind", "OPP-24101") to graph nodes |
| 3 | Router | Decides which retrieval agents run and records the reason for each, including skips |
| 4 | Graph agent | Walks 1-2 hops from each named entity in Neo4j (deals, contracts, programmes, people, partners, funding) |
| 5 | Document agent | Vector + full-text + entity-linked search over chunks, fused by rank, then a permission filter in Cypher |
| 6 | Facts agent | Read-only SQL on the SQLite fact tables, filtered to the user's scope |
| 7 | Composer | Gemini writes the answer from the evidence only, citing `[C1]`, `[C2]` … |
| 8 | Verifier | Checks every figure in the answer against the evidence and that each citation exists |

In the UI, click a citation to jump to its source, open the original file, click an agent in **Agent path** to see its
reasoning, and expand a **Trace** step to see the exact query and the first rows it returned. Sign in as a different
user to see how the same question changes.

## 5. Sign-in and access

Every page and API call except sign-in needs a session. Demo users are created the first time the backend starts, and
**all of them use the password `Demo@123`**. The sign-in page lists them; click a row to fill in the username.

| Username | Role | Can see |
| --- | --- | --- |
| `laura.chen` | Executive | Every IQ, all accounts; revenue margin hidden |
| `priya.raman` | Account Owner | Own accounts: Northwind Traders, Fabrikam Health |
| `marcus.bell` | Account Owner | Own accounts: Woodgrove Bank, Litware Insurance, Meridian Bank, Calder Insurance |
| `sophie.turner` | Account Owner | Own accounts: Tailspin Airlines, Contoso Manufacturing, Wingtip Logistics |
| `anita.rao` | GTM / Bid Manager | GTM in full; accounts limited to their pursuit accounts; revenue as totals only |
| `sarah.kim` | Inside Sales & Marketing | Campaign in full; GTM totals only; their target accounts |
| `daniel.cho` | Sales Ops / Finance | Revenue in full including margin; no Solutions or Delivery |
| `ravi.shankar` | Presales / Solutions | Solutions, GTM, Accounts and Delivery in full |
| `elena.novak` | Alliances | Partners Microsoft and AWS, and accounts linked to their deals |
| `kevin.shah` | Alliances | Partners Databricks, Snowflake, ServiceNow and Guidewire |
| `arjun.mehta` | Delivery Lead | Delivery for Northwind Traders and Wingtip Logistics |
| `admin` | Platform Admin | Settings, document loading, users and the sign-in audit; no business data |

Roles, grants and the demo user list live in `backend/app/permissions.py`; sign-in is in `backend/app/auth.py`. Account
owners, GTM, marketing, alliances and delivery leads all have the Solutions IQ in full, so they can read every proposal,
including other clients' pricing. Lower that grant to `own` in `ROLES` if that is not intended.

**How it is stored (`data/iq.db`):**

- `users`: username, role, account and partner scope, and a salted scrypt hash of the password
  (`scrypt$16384$8$1$<salt>$<hash>`). Plain-text passwords are never stored.
- `sessions`: the SHA-256 of each session token and its expiry. The browser holds the token in an HttpOnly, SameSite=Lax
  cookie `iq_session` that lasts 12 hours. Signing out deletes the row, so an old cookie stops working.
- `login_audit`: every sign-in attempt with result, reason and IP. Five wrong passwords lock a user for 10 minutes.
- `questions`: each question is saved under the user who asked it. History and `?id=` links only show your own questions.

**What is enforced on the server:**

- Document chunks are filtered in the Cypher query itself.
- Graph nodes outside your scope show their name only.
- Fact rows are filtered by account or partner.
- `/api/file` returns 403 unless you may see the whole document.
- Settings, loading and the users list return 403 for everyone except `admin`.

To reset the demo users (for example after changing `DEMO_USERS`), stop the backend and run
`sqlite3 data/iq.db "DELETE FROM users; DELETE FROM sessions;"`. They are created again on the next start.
