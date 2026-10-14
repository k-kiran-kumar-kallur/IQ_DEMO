"""Ingestion: test_documents -> file store + SQLite tables + Neo4j (entities, documents, chunks with embeddings)."""
import datetime as dt
import hashlib
import json
import re
import shutil
import threading
import time
import traceback

from . import db, embeddings, graph
from .config import CORPUS_DIR, CORPUS_EXCLUDE, RAW_DIR
from .extract import chunk_sections, extract
from .permissions import FOLDER_TO_IQ, IQS

STATE = {"running": False, "phase": "idle", "done": 0, "total": 0, "message": "", "started_at": None,
         "finished_at": None, "counts": {}, "log": []}

# canonical fact tables (file, sheet) -> SQLite view used by the facts agent and to build graph entities
CANON = {
    "v_revenue": ("Sales_Revenue/revenue_reports/Revenue_by_Account_and_Service_Line_FY2025-FY2026.xlsx", "Revenue Data"),
    "v_pipeline": ("Sales_Revenue/pipeline_reports/FocusNet_Pipeline_Report_2026-10-06.xlsx", "Open Pipeline"),
    "v_closed": ("Sales_Revenue/pipeline_reports/FocusNet_Pipeline_Report_2026-10-06.xlsx", "Closed FY2026"),
    "v_bids": ("GTM/bid_trackers/GTM_Bid_Tracker_FY2026.xlsx", "Bid Tracker"),
    "v_renewals": ("Sales_Revenue/renewals/Renewals_and_Expansion_Next_180_Days.xlsx", "Renewals"),
    "v_expansion": ("Sales_Revenue/renewals/Renewals_and_Expansion_Next_180_Days.xlsx", "Expansion"),
    "v_funding": ("Channels_Partners/funding/Partner_Funding_Tracker_FY2026.xlsx", "Funding"),
    "v_registrations": ("Channels_Partners/deal_registrations/Deal_Registration_Tracker_FY2026.xlsx", "Registrations"),
    "v_partner_pipeline": ("Channels_Partners/partner_reports/Partner_Pipeline_Report_Oct_2026.xlsx", "Partner Pipeline"),
    "v_health": ("Accounts/account_health/Account_Health_Scorecard_Sep_2026.csv", "csv"),
    "v_contacts": ("Accounts/stakeholder_reports/focusnet_contacts_export_2026-10-06.csv", "csv"),
    "v_projects": ("Delivery/programmes/Strategic_Programme_Portfolio_Q3_2026.xlsx", "Projects"),
    "v_programmes": ("Delivery/programmes/Strategic_Programme_Portfolio_Q3_2026.xlsx", "Programmes"),
    "v_attribution": ("Campaign/attribution/Campaign_Attribution_and_ROI_FY2026.xlsx", "Attribution"),
    "v_campaign_opps": ("Campaign/attribution/Campaign_Attribution_and_ROI_FY2026.xlsx", "Opportunity Map"),
}
PARTNER_MAP = "Channels_Partners/relationships/partner_relationship_map.json"
ID_RE = re.compile(r"\b(ACC-1\d{3}|OPP-2\d{4}|BID-0\d{3}|PRG-20\d\d|PRJ-3\d{3}|PRT-0\d|CMP-26\d\d|CON-5\d{3}|CTR-7\d{3}|FND-9\d\d)\b")
ALIAS_STOP = {"Adventure", "Fourth", "Wide", "Trey", "Alpine"}
LABELS = ["Account", "Opportunity", "Bid", "Contract", "Programme", "Project", "Partner", "Contact", "Campaign", "Funding",
          "Registration", "Document", "Chunk"]


def log(msg):
    STATE["log"].append(f"{dt.datetime.now().strftime('%H:%M:%S')}  {msg}")
    STATE["message"] = msg


def corpus_files():
    out = []
    for p in sorted(CORPUS_DIR.rglob("*")):
        if p.is_dir():
            continue
        rel = p.relative_to(CORPUS_DIR)
        if any(part in CORPUS_EXCLUDE for part in rel.parts) or p.name.startswith("."):
            continue
        out.append(p)
    return out


def table_name(rel, sheet):
    stub = re.sub(r"[^0-9a-zA-Z]+", "_", rel.rsplit(".", 1)[0]).lower()[-60:]
    return f"t_{stub}__{db.sanitize(sheet)}"


def account_aliases(accounts):
    """Name variants used to spot accounts in text and questions, e.g. 'Northwind' -> ACC-1001."""
    out = {}
    for aid, name in accounts.items():
        out[name] = aid
        words = name.split()
        first = words[0]
        if len(first) >= 5 and first not in ALIAS_STOP:
            out[first] = aid
        elif len(words) > 1:
            out[" ".join(words[:2])] = aid
    return out


# ------------------------------------------------------------------ SQLite fact tables
def view_rows(conn, view):
    try:
        cur = conn.execute(f"SELECT * FROM {view}")
    except Exception:
        return []
    cols = [d[0] for d in cur.description]
    return [dict(zip(cols, r)) for r in cur.fetchall()]


def build_views(conn, tables_by_key):
    for view, (rel, sheet) in CANON.items():
        t = tables_by_key.get((rel, sheet))
        conn.execute(f"DROP VIEW IF EXISTS {view}")
        if not t:
            continue
        first = conn.execute(f'SELECT * FROM "{t}" LIMIT 0').description[0][0]
        conn.execute(f'CREATE VIEW {view} AS SELECT * FROM "{t}" WHERE "{first}" IS NOT NULL AND "{first}" NOT IN (\'Total\', \'FY2026\')')


# ------------------------------------------------------------------ entities from structured exports
def build_entities(conn):
    E = {lab: {} for lab in LABELS}
    R = []                          # (from_label, from_id, rel, to_label, to_id)
    acc_names = {}

    def src(view):
        rel, sheet = CANON[view]
        return {"source_path": rel, "source_sheet": sheet}

    for r in view_rows(conn, "v_revenue"):
        acc_names[r["account_id"]] = r["account"]
        E["Account"].setdefault(r["account_id"], dict(id=r["account_id"], name=r["account"], industry=r["industry"], **src("v_revenue")))
    for r in view_rows(conn, "v_pipeline"):
        acc_names[r["account_id"]] = r["account"]
        E["Account"].setdefault(r["account_id"], dict(id=r["account_id"], name=r["account"], industry=r["industry"], **src("v_pipeline")))
    for r in view_rows(conn, "v_health"):
        a = E["Account"].setdefault(r["account_id"], dict(id=r["account_id"], name=r["account_name"], **src("v_health")))
        a.update(owner=r["account_owner"], health_status=r["health_status"], health_score=r["health_score_0_100"],
                 csat=r["csat_q3"])
    by_name = {v: k for k, v in acc_names.items()}

    for r in view_rows(conn, "v_pipeline"):
        E["Opportunity"][r["opp_id"]] = dict(id=r["opp_id"], name=r["opportunity"], stage=r["stage"], tcv=r["tcv_usd"],
                                             probability=r["probability"], close_date=r["close_date"], owner=r["owner"],
                                             service_line=r["service_line"], source=r["source"], stalled=r["stalled_flag"] or "",
                                             notes=r["notes"] or "", **src("v_pipeline"))
        R.append(("Opportunity", r["opp_id"], "FOR_ACCOUNT", "Account", r["account_id"]))
    for r in view_rows(conn, "v_closed"):
        E["Opportunity"].setdefault(r["opp_id"], dict(id=r["opp_id"], name=r["opportunity"], stage=r["result"], tcv=r["tcv_usd"],
                                                      close_date=r["close_date"], owner=r["owner"], service_line=r["service_line"],
                                                      notes=r["notes"] or "", **src("v_closed")))
        if r["account"] in by_name:
            R.append(("Opportunity", r["opp_id"], "FOR_ACCOUNT", "Account", by_name[r["account"]]))
    for r in view_rows(conn, "v_bids"):
        E["Bid"][r["bid_id"]] = dict(id=r["bid_id"], name=f"{r['bid_id']} {r['account']}", status=r["status"], type=r["bid_type"],
                                     value=r["deal_value_usd"], submission=r["submission_date"], decision=r["decision_date"],
                                     reason=r["win_loss_no_bid_reason"] or "", competitors=r["competitors"] or "", **src("v_bids"))
        if r["opportunity_id"]:
            R.append(("Bid", r["bid_id"], "FOR_OPPORTUNITY", "Opportunity", r["opportunity_id"]))
        if r["account"] in by_name:
            R.append(("Bid", r["bid_id"], "FOR_ACCOUNT", "Account", by_name[r["account"]]))
    for r in view_rows(conn, "v_renewals"):
        E["Contract"][r["contract"]] = dict(id=r["contract"], name=f"{r['contract']} {r['service']}", service=r["service"],
                                            acv=r["acv_usd"], end_date=r["contract_end"], risk=r["risk"], notes=r["notes"] or "",
                                            **src("v_renewals"))
        R.append(("Account", r["account_id"], "HAS_CONTRACT", "Contract", r["contract"]))
        if r["renewal_opp"]:
            R.append(("Contract", r["contract"], "RENEWED_BY", "Opportunity", r["renewal_opp"]))
    for r in view_rows(conn, "v_programmes"):
        E["Programme"][r["programme"]] = dict(id=r["programme"], name=r["name"], status=r["status_w40"], manager=r["programme_manager"],
                                              contract=r["contract"], **src("v_programmes"))
        if r["client"] in by_name:
            R.append(("Programme", r["programme"], "DELIVERS_FOR", "Account", by_name[r["client"]]))
    for r in view_rows(conn, "v_projects"):
        E["Project"][r["project"]] = dict(id=r["project"], name=r["project_name"], rag=r["rag_w40"], complete=r["complete"],
                                          eac=r["eac_cost"], contract_value=r["contract_value"], forecast_end=r["forecast_end"],
                                          **src("v_projects"))
        R.append(("Project", r["project"], "PART_OF", "Programme", r["programme"]))
    pmap = json.load(open(CORPUS_DIR / PARTNER_MAP, encoding="utf-8"))
    pname = {}
    for p in pmap.get("partners", []):
        pname[p["partner"]] = p["partner_id"]
        E["Partner"][p["partner_id"]] = dict(id=p["partner_id"], name=p["partner"], tier=p["tier"], status=p["programme_status"],
                                             health=p["relationship_health"], source_path=PARTNER_MAP, source_sheet="")
    for r in view_rows(conn, "v_partner_pipeline"):
        R.append(("Opportunity", r["opp_id"], "WITH_PARTNER", "Partner", r["partner_id"]))
    for r in view_rows(conn, "v_contacts"):
        E["Contact"][r["contact_id"]] = dict(id=r["contact_id"], name=r["full_name"], title=r["job_title"], role=r["buying_role"],
                                             relationship=r["relationship_strength"], status=r["status"], notes=r["notes"] or "",
                                             **src("v_contacts"))
        R.append(("Contact", r["contact_id"], "WORKS_AT", "Account", r["account_id"]))
    for r in view_rows(conn, "v_attribution"):
        E["Campaign"][r["campaign_id"]] = dict(id=r["campaign_id"], name=r["campaign"], spend=r["spend_usd"], mqls=r["mqls"],
                                               sqls=r["sqls"], pipeline_sourced=r["pipeline_sourced_usd"], **src("v_attribution"))
    for r in view_rows(conn, "v_campaign_opps"):
        R.append(("Campaign", r["campaign"], "SOURCED" if r["attribution"] == "Sourced" else "INFLUENCED", "Opportunity", r["opportunity"]))
    for r in view_rows(conn, "v_funding"):
        E["Funding"][r["funding_id"]] = dict(id=r["funding_id"], name=f"{r['funding_id']} {r['programme']}", programme=r["programme"],
                                             approved=r["approved_usd"], used=r["used_usd"], available=r["available_usd"],
                                             expires=r["expires"], status=r["status"], alert=r["expiry_alert"] or "", **src("v_funding"))
        if r["opp_id"]:
            R.append(("Funding", r["funding_id"], "FUNDS", "Opportunity", r["opp_id"]))
        if r["partner"] in pname:
            R.append(("Partner", pname[r["partner"]], "PROVIDES", "Funding", r["funding_id"]))
    for r in view_rows(conn, "v_registrations"):
        E["Registration"][r["registration_id"]] = dict(id=r["registration_id"], name=r["deal"], status=r["status"], value=r["value_usd"],
                                                       expires=r["expires"], alert=r["alert"] or "", **src("v_registrations"))
        R.append(("Registration", r["registration_id"], "REGISTERS", "Opportunity", r["opp_id"]))
        if r["partner"] in pname:
            R.append(("Registration", r["registration_id"], "WITH_PARTNER", "Partner", pname[r["partner"]]))

    # entity -> account map, so a chunk that only mentions OPP-24101 still counts as Northwind for permissions
    ent_account = {aid: aid for aid in E["Account"]}
    for f, fid, rel, t, tid in R:
        if t == "Account":
            ent_account[fid] = tid
        if f == "Account":
            ent_account[tid] = fid
    for f, fid, rel, t, tid in R:
        if f in ("Campaign", "Partner"):
            continue                       # campaigns and partners span many accounts
        if t in ("Opportunity", "Programme") and tid in ent_account and fid not in ent_account:
            ent_account[fid] = ent_account[tid]
    return E, R, ent_account


# ------------------------------------------------------------------ Neo4j writes
def neo_schema(dim, reset):
    if reset:
        for idx in ("chunk_embedding", "chunk_text"):
            graph.run(f"DROP INDEX {idx} IF EXISTS")
        while True:
            n = graph.run("MATCH (n) WITH n LIMIT 5000 DETACH DELETE n RETURN count(*) AS n")[0]["n"]
            if n == 0:
                break
    for lab in LABELS + ["IQ"]:
        key = "key" if lab == "IQ" else "id"
        graph.run(f"CREATE CONSTRAINT {lab.lower()}_{key} IF NOT EXISTS FOR (n:{lab}) REQUIRE n.{key} IS UNIQUE")
    graph.run("CREATE FULLTEXT INDEX chunk_text IF NOT EXISTS FOR (c:Chunk) ON EACH [c.text, c.section, c.doc_title]")
    graph.run("CREATE VECTOR INDEX chunk_embedding IF NOT EXISTS FOR (c:Chunk) ON (c.embedding) "
              f"OPTIONS {{indexConfig: {{`vector.dimensions`: {int(dim)}, `vector.similarity_function`: 'cosine'}}}}")


def neo_entities(E, R, ent_account):
    for lab, rows in E.items():
        if lab in ("Document", "Chunk") or not rows:
            continue
        vals = []
        for r in rows.values():
            r = {k: v for k, v in r.items() if v is not None}
            r["account_id"] = ent_account.get(r["id"])
            vals.append(r)
        for i in range(0, len(vals), 500):
            graph.run(f"UNWIND $rows AS r MERGE (n:{lab} {{id: r.id}}) SET n += r", {"rows": vals[i:i + 500]})
    groups = {}
    for f, fid, rel, t, tid in R:
        groups.setdefault((f, rel, t), []).append({"a": fid, "b": tid})
    for (f, rel, t), pairs in groups.items():
        graph.run(f"UNWIND $pairs AS p MATCH (a:{f} {{id: p.a}}) MATCH (b:{t} {{id: p.b}}) MERGE (a)-[:{rel}]->(b)",
                  {"pairs": pairs})
    graph.run("UNWIND $iqs AS q MERGE (i:IQ {key: q.key}) SET i.name = q.name",
              {"iqs": [{"key": k, "name": v} for k, v in IQS.items()]})
    return sum(len(v) for v in E.values()), len(R)


# ------------------------------------------------------------------ main
def run(reset=True):
    STATE.update(running=True, phase="starting", done=0, total=0, message="", started_at=dt.datetime.now().isoformat(),
                 finished_at=None, counts={}, log=[])
    with db.session() as c:
        run_id = c.execute("INSERT INTO ingest_runs(started_at, status) VALUES(?, 'running')", (STATE["started_at"],)).lastrowid
    try:
        graph.ping()
        files = corpus_files()
        STATE.update(phase="reading files", total=len(files))
        log(f"Found {len(files)} files in test_documents (skipping _reference/ and README.md)")
        docs, tables_by_key = [], {}
        conn = db.connect()
        for i, p in enumerate(files, 1):
            rel = str(p.relative_to(CORPUS_DIR))
            data = p.read_bytes()
            checksum = hashlib.sha256(data).hexdigest()
            doc_id = "DOC-" + hashlib.sha1(rel.encode()).hexdigest()[:10]
            iq = FOLDER_TO_IQ[rel.split("/")[0]]
            raw_rel = f"test_documents/{doc_id}/{checksum[:12]}/{p.name}"
            dest = RAW_DIR / raw_rel
            dest.parent.mkdir(parents=True, exist_ok=True)
            if not dest.exists():
                shutil.copy2(p, dest)
                (dest.parent / "checksum.sha256").write_text(checksum)
            info = extract(p)
            for t in info["tables"]:
                name = table_name(rel, t["sheet"])
                cols = db.load_table(conn, name, t["headers"], t["rows"])
                conn.execute("INSERT OR REPLACE INTO catalog VALUES(?,?,?,?,?,?)",
                             (name, rel, t["sheet"], iq, json.dumps(cols), len(t["rows"])))
                tables_by_key[(rel, t["sheet"])] = name
            docs.append(dict(id=doc_id, path=rel, title=info["title"], iq=iq, folder=rel.rsplit("/", 1)[0], format=info["format"],
                             classification=info["classification"], raw_path=raw_rel, checksum=checksum,
                             sections=info["sections"]))
            STATE["done"] = i
        build_views(conn, tables_by_key)
        conn.commit()
        log(f"Loaded {len(tables_by_key)} tables into SQLite and copied originals to data/raw")

        STATE.update(phase="building graph entities", done=0, total=1)
        E, R, ent_account = build_entities(conn)
        conn.close()
        dim = embeddings.dimension()
        neo_schema(dim, reset)
        n_ent, n_rel = neo_entities(E, R, ent_account)
        log(f"Wrote {n_ent} entities and {n_rel} relationships to Neo4j")

        # chunk + mention detection
        accounts = {k: v["name"] for k, v in E["Account"].items()}
        aliases = account_aliases(accounts)
        alias_re = re.compile(r"\b(" + "|".join(re.escape(a) for a in sorted(aliases, key=len, reverse=True)) + r")\b")
        names = {}
        for lab in ("Partner", "Contact", "Programme"):
            for k, v in E[lab].items():
                if v.get("name"):
                    names[v["name"]] = k
        name_re = re.compile(r"\b(" + "|".join(re.escape(n) for n in sorted(names, key=len, reverse=True)) + r")\b")
        label_of = {k: lab for lab, rows in E.items() for k in rows}
        known = set(label_of)
        all_chunks = []
        for d in docs:
            parts = chunk_sections(d["title"], d["sections"])
            for j, ch in enumerate(parts):
                text = ch["text"]
                mentions = set(m for m in ID_RE.findall(text) if m in known)
                mentions |= {aliases[m] for m in alias_re.findall(text)}
                mentions |= {names[m] for m in name_re.findall(text)}
                accs = sorted({ent_account[m] for m in mentions if m in ent_account})
                all_chunks.append(dict(id=f"{d['id']}-{j:03d}", doc_id=d["id"], seq=j, section=ch["section"], text=text,
                                       doc_title=d["title"], path=d["path"], iq=d["iq"], classification=d["classification"],
                                       accounts=accs, mentions=sorted(mentions)))
            d["chunks"] = len(parts)
            # chunks of an account-specific document (3 or fewer accounts) inherit the document's accounts, so a chunk that
            # never names the client is still scoped to it ("links narrow, never widen")
            doc_chunks = all_chunks[-len(parts):] if parts else []
            doc_accs = sorted({a for c in doc_chunks for a in c["accounts"]})
            if 0 < len(doc_accs) <= 3:
                for c in doc_chunks:
                    c["accounts"] = sorted(set(c["accounts"]) | set(doc_accs))
        log(f"Split documents into {len(all_chunks)} chunks; detected entity mentions")

        STATE.update(phase="embedding chunks", done=0, total=len(all_chunks))
        B = 128
        for i in range(0, len(all_chunks), B):
            batch = all_chunks[i:i + B]
            vecs = embeddings.embed_passages([f"{c['doc_title']} | {c['section']}\n{c['text']}" for c in batch])
            for c, v in zip(batch, vecs):
                c["embedding"] = v
            STATE["done"] = min(i + B, len(all_chunks))
        log(f"Embedded {len(all_chunks)} chunks locally ({dim} dimensions)")

        STATE.update(phase="writing documents and chunks", done=0, total=len(all_chunks))
        doc_rows = [{k: v for k, v in d.items() if k != "sections"} for d in docs]
        graph.run("UNWIND $docs AS d MERGE (n:Document {id: d.id}) SET n += d WITH n, d MATCH (i:IQ {key: d.iq}) MERGE (n)-[:IN_IQ]->(i)",
                  {"docs": doc_rows})
        for i in range(0, len(all_chunks), 200):
            batch = all_chunks[i:i + 200]
            rows = [{k: v for k, v in c.items() if k != "mentions"} for c in batch]
            graph.run("UNWIND $rows AS r MERGE (c:Chunk {id: r.id}) SET c += r "
                      "WITH c, r MATCH (d:Document {id: r.doc_id}) MERGE (d)-[:HAS_CHUNK]->(c)", {"rows": rows})
            by_label = {}
            for c in batch:
                for m in c["mentions"]:
                    by_label.setdefault(label_of[m], []).append({"c": c["id"], "e": m})
            for lab, pairs in by_label.items():
                graph.run(f"UNWIND $pairs AS p MATCH (c:Chunk {{id: p.c}}) MATCH (e:{lab} {{id: p.e}}) MERGE (c)-[:MENTIONS]->(e)",
                          {"pairs": pairs})
            STATE["done"] = min(i + 200, len(all_chunks))
        graph.run("MATCH (d:Document)-[:HAS_CHUNK]->(:Chunk)-[:MENTIONS]->(a:Account) MERGE (d)-[:ABOUT]->(a)")
        graph.run("CALL db.awaitIndexes(300)")
        with db.session() as c:
            c.execute("DELETE FROM documents")
            c.executemany("INSERT INTO documents VALUES(?,?,?,?,?,?,?,?,?,?)",
                          [(d["id"], d["path"], d["title"], d["iq"], d["format"], d["classification"], d["checksum"],
                            d["raw_path"], d["chunks"], dt.datetime.now().isoformat()) for d in docs])
        counts = dict(files=len(docs), chunks=len(all_chunks), entities=n_ent, relationships=n_rel, tables=len(tables_by_key))
        STATE.update(phase="done", counts=counts, finished_at=dt.datetime.now().isoformat())
        log(f"Done: {counts}")
        with db.session() as c:
            c.execute("UPDATE ingest_runs SET finished_at=?, status='done', files=?, chunks=?, entities=?, tables_loaded=?, message=? "
                      "WHERE id=?", (STATE["finished_at"], len(docs), len(all_chunks), n_ent, len(tables_by_key), "ok", run_id))
        from .agents import resolver
        resolver.invalidate()
    except Exception as e:
        STATE.update(phase="failed", finished_at=dt.datetime.now().isoformat())
        log(f"FAILED: {e}")
        STATE["log"].append(traceback.format_exc()[-1500:])
        with db.session() as c:
            c.execute("UPDATE ingest_runs SET finished_at=?, status='failed', message=? WHERE id=?",
                      (STATE["finished_at"], str(e)[:500], run_id))
    finally:
        STATE["running"] = False


def start(reset=True):
    if STATE["running"]:
        return False
    threading.Thread(target=run, kwargs={"reset": reset}, daemon=True).start()
    return True

