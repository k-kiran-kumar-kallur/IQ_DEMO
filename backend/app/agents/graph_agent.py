"""Graph agent: walks Neo4j outward from each named entity and returns what is connected, with the paths it took."""
from .. import graph

# which IQ owns each kind of node (used to hide nodes the user cannot see)
LABEL_IQ = {"Account": "accounts", "Opportunity": "revenue", "Bid": "gtm", "Contract": "revenue", "Programme": "delivery",
            "Project": "delivery", "Contact": "accounts", "Campaign": "campaign", "Funding": "partners", "Registration": "partners",
            "Partner": "partners"}
ALT_IQ = {"Opportunity": "gtm"}          # a GTM grant also shows deals

CYPHER = """
MATCH (s:{label} {{id: $id}})
OPTIONAL MATCH (s)-[r1]-(n1)
WHERE NOT n1:Chunk AND NOT n1:Document AND NOT n1:IQ
WITH s, collect(DISTINCT {{rel: type(r1), out: startNode(r1) = s, label: labels(n1)[0], node: properties(n1)}}) AS hop1
OPTIONAL MATCH (s)-[]-(m)-[r2]-(n2)
WHERE (m:Opportunity OR m:Programme OR m:Contract) AND NOT n2:Chunk AND NOT n2:Document AND NOT n2:IQ AND n2 <> s
WITH s, hop1, collect(DISTINCT {{via: m.id, rel: type(r2), out: startNode(r2) = m, label: labels(n2)[0], node: properties(n2)}})[0..40] AS hop2
OPTIONAL MATCH (s)<-[:MENTIONS]-(:Chunk)<-[:HAS_CHUNK]-(d:Document)
RETURN properties(s) AS start, hop1, hop2, count(DISTINCT d) AS documents
"""


def visible(label, node, ctx):
    iq = LABEL_IQ.get(label, "accounts")
    level = ctx["grants"].get(iq)
    if level not in ("full", "own") and ALT_IQ.get(label):
        iq = ALT_IQ[label]
        level = ctx["grants"].get(iq)
    if level == "full":
        return True
    if level == "own":
        acc = node.get("account_id") or (node.get("id") if label == "Account" else None)
        return acc is None or acc in ctx["own_accounts"]
    return False


def money(v):
    try:
        v = float(v)
    except (TypeError, ValueError):
        return str(v)
    return f"${v / 1e6:,.2f}M" if v >= 1e6 else f"${v:,.0f}"


def describe(label, n):
    g = n.get
    if label == "Account":
        bits = [g("industry"), f"owner {g('owner')}" if g("owner") else None,
                f"health {g('health_status')} ({g('health_score')})" if g("health_status") else None,
                f"CSAT {g('csat')}" if g("csat") else None]
    elif label == "Opportunity":
        bits = [g("stage"), f"TCV {money(g('tcv'))}" if g("tcv") else None,
                f"probability {float(g('probability')):.0%}" if g("probability") not in (None, "") else None,
                f"close {g('close_date')}" if g("close_date") else None, "STALLED" if g("stalled") else None, g("notes")]
    elif label == "Bid":
        bits = [g("type"), g("status"), money(g("value")) if g("value") else None, f"decision {g('decision')}" if g("decision") else None,
                g("reason")]
    elif label == "Contract":
        bits = [f"ACV {money(g('acv'))}" if g("acv") else None, f"ends {g('end_date')}", f"risk {g('risk')}", g("notes")]
    elif label == "Programme":
        bits = [f"status {g('status')}", g("contract"), f"manager {g('manager')}" if g("manager") else None]
    elif label == "Project":
        bits = [f"RAG {g('rag')}", f"{float(g('complete')):.0%} complete" if g("complete") not in (None, "") else None,
                f"EAC {money(g('eac'))}" if g("eac") else None, f"forecast end {g('forecast_end')}" if g("forecast_end") else None]
    elif label == "Contact":
        bits = [g("title"), g("role"), f"relationship {g('relationship')}", g("status"), g("notes")]
    elif label == "Funding":
        bits = [g("programme"), f"approved {money(g('approved'))}", f"used {money(g('used'))}", f"expires {g('expires')}",
                g("alert") or None]
    elif label == "Registration":
        bits = [g("status"), f"expires {g('expires')}" if g("expires") else None, g("alert") or None]
    elif label == "Campaign":
        bits = [f"spend {money(g('spend'))}", f"{g('mqls')} MQLs" if g("mqls") else None]
    elif label == "Partner":
        bits = [g("tier"), g("health")]
    else:
        bits = []
    return "; ".join(str(b) for b in bits if b not in (None, "", "None"))


def run(entities, ctx, step, cid_start):
    evidence, nodes, edges, paths = [], {}, [], []
    hidden = 0
    for e in entities[:4]:
        rows = graph.run(CYPHER.format(label=e["label"]), {"id": e["id"]}, step=step,
                         label=f"Walk out from {e['label']} {e['id']} ({e['name']})")
        if not rows or not rows[0]["start"]:
            continue
        r = rows[0]
        s = r["start"]
        nodes[s["id"]] = dict(id=s["id"], label=e["label"], name=s.get("name"), root=True)
        if visible(e["label"], s, ctx):
            lines = [f"{e['label']} {s['id']} {s.get('name', '')}: {describe(e['label'], s)}"]
        else:
            lines = [f"{e['label']} {s['id']} {s.get('name', '')}: details withheld (outside this user's access)"]
            step.notes.append(f"Starting node {s['id']} is outside this user's access: only its name is used; "
                              "connected records are shown only where the user's grants allow.")
        sources = {s.get("source_path")}
        for h in sorted(r["hop1"], key=lambda h: (h["label"], h["node"].get("id", ""))):
            n = h["node"]
            if not n.get("id"):
                continue
            if not visible(h["label"], n, ctx):
                hidden += 1
                continue
            nodes.setdefault(n["id"], dict(id=n["id"], label=h["label"], name=n.get("name")))
            a, b = (s["id"], n["id"]) if h["out"] else (n["id"], s["id"])
            edges.append(dict(source=a, target=b, type=h["rel"]))
            arrow = f"-[{h['rel']}]->" if h["out"] else f"<-[{h['rel']}]-"
            paths.append(f"({s['id']}) {arrow} ({n['id']})")
            lines.append(f"  {arrow} {h['label']} {n['id']} {n.get('name', '')}: {describe(h['label'], n)}")
            sources.add(n.get("source_path"))
        for h in r["hop2"]:
            n = h["node"]
            if not n.get("id") or n["id"] in nodes and nodes[n["id"]].get("root"):
                continue
            if not visible(h["label"], n, ctx):
                hidden += 1
                continue
            new = n["id"] not in nodes
            nodes.setdefault(n["id"], dict(id=n["id"], label=h["label"], name=n.get("name")))
            a, b = (h["via"], n["id"]) if h["out"] else (n["id"], h["via"])
            edges.append(dict(source=a, target=b, type=h["rel"]))
            if new:
                arrow = f"-[{h['rel']}]->" if h["out"] else f"<-[{h['rel']}]-"
                paths.append(f"({s['id']}) - ({h['via']}) {arrow} ({n['id']})")
                lines.append(f"    via {h['via']} {arrow} {h['label']} {n['id']} {n.get('name', '')}: {describe(h['label'], n)}")
                sources.add(n.get("source_path"))
        cid = f"C{cid_start + len(evidence)}"
        srcs = sorted(x for x in sources if x)
        evidence.append(dict(cid=cid, kind="graph", title=f"Graph: {e['label']} {s['id']} {s.get('name', '')}",
                             source_path=srcs[0] if srcs else "", sources=srcs, iq=LABEL_IQ.get(e["label"], "accounts"),
                             text="\n".join(lines[:40]),
                             why=[f"Named in the question ({e['how']}: '{e['matched']}')",
                                  f"{len(lines) - 1} connected record(s) within 2 hops",
                                  f"Mentioned in {r['documents']} document(s)"]))
        step.items.append(dict(evidence=cid, start=f"{e['label']} {s['id']}", connected=len(lines) - 1, documents=r["documents"]))
    if hidden:
        step.notes.append(f"{hidden} connected node(s) hidden: they belong to an IQ or account this user cannot see.")
    # de-duplicate edges
    seen, uniq = set(), []
    for ed in edges:
        k = (ed["source"], ed["target"], ed["type"])
        if k not in seen and ed["source"] in nodes and ed["target"] in nodes:
            seen.add(k)
            uniq.append(ed)
    step.data = dict(nodes=list(nodes.values())[:60], edges=uniq[:120], paths=paths[:60])
    step.summary = f"{len(nodes)} node(s), {len(uniq)} relationship(s) from {len(evidence)} starting point(s)"
    return evidence
