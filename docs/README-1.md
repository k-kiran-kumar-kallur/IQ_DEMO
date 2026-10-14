# Visionet Enterprise IQ - Demo

A demo of Enterprise IQ: seven "IQs" (GTM, Campaign, Accounts, Revenue, Solutions, Partners,
Delivery) that turn data spread across many systems into a daily, permission-aware view for
each person, with AI agents on Claude (Amazon Bedrock).

- **Frontend:** React 19, TypeScript, Vite, MUI
- **Backend:** FastAPI, SQLAlchemy, Alembic, SQLite
- **Security:** session cookies, role-based access from `backend/app/policy/catalog.yaml`, and a tamper-evident (hash-chained) audit log

For a full product and system guide (pages, agents, schedules, data sources, governance),
see **[APPLICATION.md](APPLICATION.md)**. For AI agents and how they communicate, see
**[AGENTS.md](AGENTS.md)**. For demo users and what each can access, see
**[USERS.md](USERS.md)**. For a plain-language brief for managers and clients (each IQ,
agents, how data is read), see **[CLIENT_BRIEF.md](CLIENT_BRIEF.md)**. For connecting real
systems instead of dummy data (what to ask your manager), see
**[INTEGRATIONS.md](INTEGRATIONS.md)**. This README covers quick start and demo walkthrough.

## Quick start (Windows / PowerShell)

Prerequisites: Python 3.12 or newer, Node.js 22 or newer.

```powershell
.\scripts\setup.ps1            # venv, packages, backend\.env, demo database
.\scripts\start-backend.ps1    # API on http://127.0.0.1:8000  (docs: /api/docs)
.\scripts\start-frontend.ps1   # app on http://localhost:5173   (second terminal)
```

Open http://localhost:5173 and sign in with any demo user below. The login page also lists
them, and you can click one to sign in.

Other commands:

| Command | What it does |
| --- | --- |
| `.\scripts\setup.ps1 -KeepData` | Re-run setup without wiping the database |
| `.\scripts\check.ps1` | Backend tests and ruff, frontend type check and ESLint |
| `backend\.venv\Scripts\python -m app.cli reset-demo` | Regenerate sample data, recreate the demo database and sync every sample source (stop the backend first) |
| `backend\.venv\Scripts\python -m app.cli sample-data` | Regenerate only the sample data files in `backend\sample_data` |

If PowerShell blocks the scripts, run `Set-ExecutionPolicy -Scope CurrentUser RemoteSigned` once.

## Demo users

All demo users have the password **`Demo@123`**. They only exist when `DEMO_MODE=true`.

| Username | Role | What they should see |
| --- | --- | --- |
| `exec` | Executive | Every IQ, all accounts |
| `gtm.lead` | GTM / Bid Manager | GTM (write), revenue as totals only; accounts limited to Woodgrove Bank, Tailspin Airlines, Contoso Manufacturing |
| `marketing` | Inside Sales and Marketing | Campaign (write), GTM as totals only; accounts limited to Woodgrove Bank, Litware Insurance, Adventure Works Retail |
| `account.owner` | Account Owner / Client Partner | Every IQ, but only for Northwind Traders and Fabrikam Health |
| `finance` | Sales Ops / Finance | Revenue (write), GTM, Campaign, Accounts, Partners |
| `presales` | Presales / Solutions | Solutions (write), GTM, Accounts, Delivery |
| `alliances` | Alliances / Partner Manager | Partners (write) for Microsoft and AWS; revenue as totals only |
| `delivery` | Delivery Lead | Delivery (write) for Northwind Store Modernisation and Wingtip Fleet Analytics |
| `admin` | Platform Admin | Users and Roles, Agents, Data Sources, Audit Log. No business data |
| `datasteward` | Data Steward | Data Sources (add, test, sync). No business data |
| `auditor` | Compliance Auditor | Audit Log and user directory, read-only |

Every sign-in, successful or failed, is written to the audit log. Sign in as `auditor` or
`admin` and open **Audit Log** to see the entries and verify the hash chain.

## Data sources

There are no real systems in the demo. `reset-demo` generates fictional data for all 36 data
areas in the approach document and connects it through 14 pre-configured **sample sources**,
one or more for each system in the landscape: FocusNet (CSV export and a simulated API),
SysHCM (Excel and a SQL database), HubSpot (JSON export and a simulated API), SharePoint
libraries, Enterprise IQ Hub lists, Copilot transcripts, partner portals (simulated API),
an external news feed, the delivery platform, the project artefact repository and delivery
mail. The simulated APIs live under `/mock-api` and only exist in demo mode.

Sample sources are ordinary data sources. To go live, add the real system as a new source
with the same mapping and disable the sample one.

- **Data Sources** (`datasteward`, `admin`): add a source with the wizard (pick a connector,
  configure it or upload a CSV / Excel / JSON file, test, map streams to Enterprise IQ
  entities, set access, save and sync). Each source has tabs for mappings, sync history,
  records, access and its own audit trail. Secrets are encrypted and never shown again.
- **Access per source:** which IQs it feeds, classification (internal / confidential /
  restricted), visibility (everyone with IQ access, or selected roles and people), owners,
  and field rules that hide or mask a field except for chosen roles. Access managers can
  preview the records exactly as any user would see them.
- **Data Access** (`admin`): a matrix of every source against every business role.

Things to try: `finance` sees revenue margins and `exec` doesn't (the field is hidden);
`gtm.lead` sees revenue as totals only; `account.owner` sees only Northwind and Fabrikam rows;
`marketing` sees lead emails and everyone else sees them masked; only `exec` and `finance`
can open the restricted SysHCM database; `delivery` owns the delivery mail source and can
change its access without being an admin.

## IQ dashboards

Each of the 7 IQs has tabs covering every data area in the approach document (40 tabs), with
KPIs, charts, tables and intel cards built from the synced sample data. Every tab lists the
sources it drew on.

What a user sees on a tab depends on their grant for that IQ, plus the access rules on each
source:

- **All records:** the full picture.
- **Own (team) scope:** only the user's accounts, partners or programmes. A banner says so.
- **Totals only:** KPIs and trend charts, with no rows, cards or per-account breakdowns.
- **Field rules:** a hidden field is also left out of every total. For example, margin is
  hidden from `exec`, so the Revenue tab shows no average margin for that user.
- **Withheld sources:** sources the user can't open are named in a banner, never shown.

The other IQ pages:

- **Account 360** (Accounts IQ tab): one account across every IQ the user can see.
- **Executive Overview** (`/overview`): headline numbers from each IQ the user has access to.
- **IQ Hub** (`/hub`): full-text search (SQLite FTS5) over documents and intel. Results are
  filtered per item: a document is visible only through the IQs it belongs to, so
  library-wide Solutions access doesn't expose another team's account plans.

Things to try:

- Open **Revenue IQ → Pipeline** as `exec` and then as `account.owner` (Northwind and
  Fabrikam only).
- Open **Revenue IQ → Revenue** as `gtm.lead` (totals only) and as `finance` (with margin).
- Open **Revenue IQ → Bookings** as `account.owner`: the restricted SysHCM database is
  withheld.
- Search the Hub for "renewal workshop" as `delivery` and then as `gtm.lead`.

## AI agents

The agents run on Claude through the Amazon Bedrock Converse API. The composer and the Pulse
use `ANTHROPIC_MODEL`; the seven IQ agents and transcript extraction use the faster
`CHAT_HISTORY_CONTINUE_MODEL`. With `LLM_PROVIDER=mock`, a deterministic offline model
follows the same tool-use protocol (the tests use it).

How a question is answered:

1. The **Ask IQ composer** can only call agents for the IQs the user has a grant on.
2. Each **IQ agent** reads data only through the **tool gateway** (`app/agents/tools.py`). The
   gateway runs as the user, through the same `IqScope` / data-source checks as the
   dashboards, so the model never receives a record the user couldn't open. Every tool
   result gets a citation ID, and every call is audited.
3. The answer cites its sources (`[C1]` chips), and a **verifier** checks every figure in it
   against the numbers the tools returned.
4. **How this was answered** shows each agent, model round and tool call. Anything withheld
   by access rules (totals-only IQs, hidden fields, withheld sources) is listed under the
   answer.

The other agent features:

- **Signals** (`app/signals/rules.py`): 12 SQL rules across the seven IQs. Examples: bid
  decision due, stalled deal, renewal at risk, revenue drop, partner funding expiring, MQL
  spike, trigger event, competitor mention, red account or programme. Rules are evaluated
  live per user; with totals-only access a rule shows a count, not records.
- **Daily IQ Pulse**: a personal brief on Home built from the user's signals and IQ
  summaries, cited and number-checked. Use "Generate now", or let the daily job run at
  `PULSE_HOUR` UTC (APScheduler, `SCHEDULER_ENABLED`). Each Pulse is posted to the user's
  in-app **Teams channel** (`/teams`), a stand-in for Microsoft Teams behind a `Notifier`
  interface.
- **Capture meeting intel** (`/capture`, needs write access to Accounts or GTM IQ): paste a
  transcript or pick one, review the extracted priorities, pain points, competitors,
  commitments and next steps, and save them as meeting intel. Changes the meeting implies
  for an opportunity or bid become **approvals**.
- **Approvals** (`/approvals`): opportunity changes go to Sales Ops / Finance and bid changes
  go to the GTM team. A requester can never approve their own change, and approving applies
  it and writes an audit entry.

Things to try:

- As `exec`, generate the Pulse on Home, then open **Teams Channel**.
- Ask "Which deals are stalled and which renewals are at risk?" as `exec`, then as
  `account.owner` (own accounts only) and `gtm.lead` (revenue totals only, noted under the
  answer).
- As `account.owner`, capture intel for Northwind Traders with the sample transcript and
  keep the proposed risk change. Then sign in as `finance` and approve it.

## Governance

- **Agents** (`/agents`, `agent.read`; the switch needs `agent.manage`): a manifest for the
  composer, the seven IQ agents, the Pulse writer and the meeting-intel extractor. Each
  card shows what the agent may call, which IQs it touches, its autonomy, owner, sponsor
  and budget. Turning an agent off stops it immediately: Ask IQ, Pulse and Capture refuse
  a disabled top-level agent, and a disabled IQ agent is left out of the answer with a
  note. Platform Admin can switch agents; the auditor can view them.
- **Run log**: the last runs, with tokens, an estimated cost and a redacted trace (which
  agent called which tool, and whether a call was denied). The question, the answer and
  the tool data stay in that user's conversation or Pulse.
- **Workflows** (`/workflows`, `workflow.read`; running or switching needs
  `workflow.manage`): the daily Pulse, hourly data-source sync, and high-signal alerts
  posted to the Teams **Alerts** channel. Each job has a switch, a schedule, the next run
  and its last ten runs. "Run now" starts the job in the background.
- **Why can I see this?** on My Access explains every data source for the signed-in user:
  allowed or not, the record scope, the reasons, and any fields hidden or masked.
- **Approvals** shows a count of requests waiting for you in the menu. An approved field
  change is kept on the record, so a later sync from the source does not undo it.

A demo walkthrough:

1. Sign in as `exec`. On Home, generate the Pulse. Open **Teams Channel** and switch to
   Alerts after an administrator has run the alerts workflow (step 4).
2. Ask IQ "Which bids are due and what is the win rate?" Open **How this was answered**.
3. Open **My Access** and read **Why can I see this?** Compare it with `account.owner`
   (own records) and `marketing` (no Sales IQ sources).
4. Sign in as `admin`. Open **Agents**, turn off the GTM IQ agent, then ask the same
   question as `exec`: the answer says that agent was not consulted. Turn it back on.
   Open **Workflows** and run **High-signal alerts**, then check the run result.
5. As `account.owner`, capture intel and propose a risk change. As `finance`, the
   Approvals item shows a badge; approve the change. Sync the source again from Data
   Sources: the approved value is still there.

## Project layout

```
backend/
  app/
    api/v1/        REST endpoints (auth, users, audit, policy, data sources, IQ, health)
    auth/          sessions, login provider, FastAPI dependencies
    audit/         hash-chained audit sink
    policy/        catalog.yaml (roles, permissions, IQ domains) and the policy engine
    access/        data-source access rules (IQ grant, visibility, classification, scope, field rules)
    iq/            per-IQ scope, section builders for the 40 tabs, Account 360, overview, Hub search
    llm/           LLM provider interface, Bedrock (Converse) and offline mock providers
    agents/        tool gateway, the seven IQ agents, Ask IQ composer, number verifier, registry
    signals/       signal and alert rules for all seven IQs
    pulse.py       Daily IQ Pulse
    workflows.py   scheduled jobs (Pulse, source sync, high-signal alerts); scheduler.py runs them
    notify.py      in-app Teams posts (Pulse, alerts, approval decisions)
    capture.py     meeting-intel extraction and save; approvals.py applies approved changes
    connectors/    CSV/Excel, JSON, document folder, REST (SSRF-guarded), SQL (read-only)
    ingestion/     entity registry, mapping suggestions, value coercion, sync runner
    secrets/       encrypted storage for connector secrets
    mock_systems/  simulated FocusNet, HubSpot and partner-portal APIs (demo mode only)
    models/        SQLAlchemy models (users, audit, data sources, canonical IQ data)
    seed/          demo users, sample data generator, sample sources
    cli.py         migrate | sample-data | seed | reset-demo
  sample_data/     generated sample files (git-ignored)
  alembic/         database migrations
  tests/           pytest suite
frontend/
  src/
    auth/          login state, route guards, access helpers
    layout/        app shell and role-filtered navigation
    components/iq/ generic section renderer (KPIs, Recharts charts, data grids, intel cards)
    components/agents/ cited Markdown, verification chip, trace panel, signal list
    pages/         Home (Pulse), IQ pages, Overview, Hub, Ask IQ, Teams, Capture, Approvals,
                   Agents, Workflows, My Access, admin pages
    api/           typed API client
scripts/           setup, start and check scripts
docs/              Enterprise IQ approach document
```

## Configuration

Backend settings live in `backend/.env` (created by `setup.ps1` from `backend/.env.example`).
Never commit `.env` files. `LLM_PROVIDER=bedrock` needs `AWS_REGION`, the AWS keys and
`ANTHROPIC_MODEL` (optionally `CHAT_HISTORY_CONTINUE_MODEL` for the faster agent model).
Set `LLM_PROVIDER=mock` to work offline. `SCHEDULER_ENABLED` and `PULSE_HOUR` (UTC) control
the daily Pulse job. The source-sync and alert jobs use the same scheduler.

`docker-compose.yml` can start the API and the frontend together. It was not run in the
environment where it was added, so treat `.\scripts\setup.ps1` and the start scripts as the
supported way to run the demo.

## Milestones

| Milestone | Scope | Status |
| --- | --- | --- |
| M1: Foundation | Skeleton, login, demo users, roles and permissions, audit log, app layout | Done |
| M2: Data Sources | Add, test and sync connections, sample data, CSV/Excel upload, per-source access control | Done |
| M3: IQ Dashboards | Seven IQ pages (40 tabs), Account 360, Executive Overview, IQ Hub search, all filtered per user | Done |
| M4: AI Agents | Seven IQ agents, Ask IQ with citations and checks, signals, daily IQ Pulse, Teams feed, meeting-intel capture, approvals | Done |
| M5: Governance | Agent kill switches and run log, scheduled workflows, access explanations, approvals that survive a re-sync | Done |
