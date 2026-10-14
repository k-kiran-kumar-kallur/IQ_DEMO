"""Runs the agents in order and builds the trace: permissions -> entity resolver -> router -> graph / documents / facts ->
composer -> verifier."""
import datetime as dt
import traceback

from .. import db, graph
from ..permissions import IQS, context
from . import composer, docs_agent, facts, graph_agent, resolver, router, verifier
from .trace import Trace

AGENT_ORDER = ["Permissions", "Entity resolver", "Router", "Graph agent", "Document agent", "Facts agent", "Composer", "Verifier"]


def _guard(trace, s, fn):
    try:
        return fn()
    except Exception as ex:
        s.status = "error"
        s.notes.append(f"{type(ex).__name__}: {str(ex)[:300]}")
        s.data["traceback"] = traceback.format_exc()[-1200:]
        return None
    finally:
        trace.end(s)


def ask(question, user):
    """`user` is the logged-in user record (auth.get_user)."""
    trace = Trace(question, user["username"])

    # 1. permissions
    s = trace.step("Permissions", "Build the permission context")

    def _perm():
        partner_accounts = []
        if user.get("partners"):
            rows = graph.run("MATCH (p:Partner)<-[:WITH_PARTNER]-(:Opportunity)-[:FOR_ACCOUNT]->(a:Account) WHERE p.id IN $p "
                             "RETURN collect(DISTINCT a.id) AS accounts", {"p": user["partners"]}, step=s,
                             label=f"Derive accounts from the user's partners ({', '.join(user['partners'])})")
            partner_accounts = rows[0]["accounts"] if rows else []
        ctx = context(user, partner_accounts)
        s.reason = "Every answer starts from what this user may see. All later agents filter with this context."
        s.items = [dict(iq=IQS[k], access={"full": "Full", "own": "Own accounts only", "aggregate": "Totals only"}
                        .get(ctx["grants"].get(k), "No access")) for k in IQS]
        s.summary = (f"{ctx['name']} ({ctx['role_name']}): {len(ctx['full'])} full, {len(ctx['own'])} own-scope, "
                     f"{len(ctx['aggregate'])} totals-only IQs")
        if ctx["own_accounts"]:
            s.notes.append("Own-scope accounts: " + ", ".join(ctx["own_accounts"]))
        s.notes.append(ctx["note"])
        return ctx
    ctx = _guard(trace, s, _perm) or context(user)
    if user.get("partners"):
        s.notes.insert(0, "Own-scope partners: " + ", ".join(user["partners"]))

    # 2. entity resolver
    s = trace.step("Entity resolver", "Find the accounts, deals, programmes, partners and people named")
    s.reason = ("Questions name things in many ways ('Northwind', 'ACC-1001', 'Atlas'). The resolver maps them to graph IDs "
                "so the other agents work on exact records.")
    entities = _guard(trace, s, lambda: resolver.resolve(question, ctx, s)) or []
    s.summary = (", ".join(f"{e['name']} ({e['id']})" for e in entities[:5]) or "No named entities") if s.status == "ran" else s.summary

    # 3. router
    s = trace.step("Router", "Decide which agents run, and why")
    s.reason = "Picks the retrieval paths this question needs, based on named entities and the kind of facts asked for."
    plan = _guard(trace, s, lambda: router.plan(question, entities, ctx, s)) or ([], {})
    decisions, intents = plan
    run_map = {d["agent"]: d for d in decisions}

    evidence = []
    # 4. graph agent
    d = run_map.get("Graph agent")
    if d and d["run"]:
        s = trace.step("Graph agent", "Walk the knowledge graph from the named entities")
        s.reason = d["reason"]
        evidence += _guard(trace, s, lambda: graph_agent.run(entities, ctx, s, len(evidence) + 1)) or []
    else:
        trace.skip("Graph agent", "Walk the knowledge graph", d["reason"] if d else "Router did not run")
    # 5. document agent
    d = run_map.get("Document agent")
    if d and d["run"]:
        s = trace.step("Document agent", "Hybrid search over document chunks")
        s.reason = d["reason"]
        evidence += _guard(trace, s, lambda: docs_agent.run(question, entities, ctx, s, len(evidence) + 1)) or []
    else:
        trace.skip("Document agent", "Hybrid search over document chunks", d["reason"] if d else "Router did not run")
    # 6. facts agent
    d = run_map.get("Facts agent")
    if d and d["run"]:
        s = trace.step("Facts agent", "Query the SQLite fact tables")
        s.reason = d["reason"]
        evidence += _guard(trace, s, lambda: facts.run(d.get("intents", []), entities, ctx, question, s, len(evidence) + 1)) or []
    else:
        trace.skip("Facts agent", "Query the SQLite fact tables", d["reason"] if d else "Router did not run")

    # 7. composer
    s = trace.step("Composer", "Write the answer from the evidence")
    out = _guard(trace, s, lambda: composer.compose(question, evidence, s))
    answer, llm = out if out else ("The answer could not be generated; see the trace.", {})
    s.summary = f"{llm.get('provider', '')} {llm.get('model', '')}".strip()

    # 8. verifier
    s = trace.step("Verifier", "Check numbers and citations")
    ver = _guard(trace, s, lambda: verifier.verify(answer, evidence, s)) or {"status": "not checked", "cited": []}

    steps = trace.to_list()
    path = []
    for name in AGENT_ORDER:
        st = next((x for x in steps if x["agent"] == name), None)
        if st:
            path.append(dict(agent=name, status=st["status"], ms=st["ms"], summary=st["summary"], reason=st["reason"]))
    graph_step = next((x for x in steps if x["agent"] == "Graph agent" and x["status"] == "ran"), None)
    result = dict(question=question, user=user["username"], user_name=f"{ctx['name']} ({ctx['role_name']})", asked_at=dt.datetime.now().isoformat(timespec="seconds"),
                  answer=answer, status=ver["status"], verification=ver, total_ms=trace.total_ms(), llm=llm,
                  evidence=evidence, steps=steps, path=path, subgraph=(graph_step or {}).get("data", {}),
                  entities=[dict(id=e["id"], label=e["label"], name=e["name"]) for e in entities])
    result["id"] = db.save_question(result)
    return result
