"""Document agent: hybrid retrieval over chunks in Neo4j (vector + full-text + entity-linked), permission-filtered."""
import re

from .. import embeddings, graph
from ..permissions import chunk_allowed_cypher

STOP = set("""a an the and or of to in on for with by at from is are was were be been being what which who whom whose why how
when where do does did can could should would will shall may might our we us you your their they them it its this that these
those there here about into over under than then so as if not no yes any all some more most much many tell me show give list
please explain status latest current""".split())
TOP_K = 8
PER_DOC = 2


def lucene_query(question, entities):
    words = [w for w in re.findall(r"[A-Za-z0-9][A-Za-z0-9\-]+", question) if w.lower() not in STOP and len(w) > 2]
    words += [e["name"] for e in entities if e.get("name")]
    esc = lambda s: re.sub(r'([+\-!(){}\[\]^"~*?:\\/]|&&|\|\|)', r"\\\1", s)
    terms = []
    for w in words:
        terms.append(f'"{esc(w)}"' if " " in w else esc(w))
    return " OR ".join(dict.fromkeys(terms)) or "*"


def run(question, entities, ctx, step, cid_start):
    vec = embeddings.embed_query(question)
    lists = {}
    try:
        rows = graph.run("CALL db.index.vector.queryNodes('chunk_embedding', 60, $vec) YIELD node, score "
                         "RETURN node.id AS id, score", {"vec": vec}, step=step,
                         label="Vector search: 60 nearest chunks by meaning (cosine)")
    except Exception:
        rows = graph.run("CYPHER 25 MATCH (c:Chunk) SEARCH c IN (VECTOR INDEX chunk_embedding FOR $vec LIMIT 60) SCORE AS score "
                         "RETURN c.id AS id, score", {"vec": vec}, step=step, label="Vector search (SEARCH clause)")
    lists["vector"] = rows
    q = lucene_query(question, entities)
    lists["keyword"] = graph.run("CALL db.index.fulltext.queryNodes('chunk_text', $q, {limit: 40}) YIELD node, score "
                                 "RETURN node.id AS id, score", {"q": q}, step=step,
                                 label="Keyword search: full-text index on chunk text")
    ids = [e["id"] for e in entities]
    if ids:
        lists["entity"] = graph.run("MATCH (c:Chunk)-[:MENTIONS]->(e) WHERE e.id IN $ids WITH DISTINCT c "
                                    "RETURN c.id AS id, vector.similarity.cosine(c.embedding, $vec) AS score "
                                    "ORDER BY score DESC LIMIT 40", {"ids": ids, "vec": vec}, step=step,
                                    label="Entity-linked: chunks that MENTION the named entities, ranked by meaning")
    # reciprocal rank fusion
    fused = {}
    for name, rows in lists.items():
        for rank, r in enumerate(rows, 1):
            f = fused.setdefault(r["id"], {"rrf": 0.0, "ranks": {}})
            f["rrf"] += 1.0 / (60 + rank)
            f["ranks"][name] = (rank, round(r["score"], 3))
    cand = sorted(fused, key=lambda k: -fused[k]["rrf"])[:80]
    details = graph.run(
        "MATCH (d:Document)-[:HAS_CHUNK]->(c:Chunk) WHERE c.id IN $ids "
        "RETURN c.id AS id, c.text AS text, c.section AS section, c.iq AS iq, c.accounts AS accounts, "
        "c.classification AS classification, d.id AS doc_id, d.title AS title, d.path AS path, d.format AS format, "
        f"d.raw_path AS raw_path, {chunk_allowed_cypher('c')} AS allowed",
        {"ids": cand, "full": ctx["full"], "own": ctx["own"], "own_accounts": ctx["own_accounts"]}, step=step,
        label="Fetch candidates and apply the permission filter (IQ grant + account scope)", sample=3)
    by_id = {d["id"]: d for d in details}
    allowed = [k for k in cand if by_id.get(k, {}).get("allowed")]
    denied = [k for k in cand if k in by_id and not by_id[k]["allowed"]]
    denied_iqs = sorted({by_id[k]["iq"] for k in denied})
    if denied:
        step.notes.append(f"Permission filter removed {len(denied)} of {len(cand)} candidate chunks "
                          f"(from {', '.join(denied_iqs)} IQ content outside this user's grants or account scope).")
    picked, per_doc = [], {}
    for k in allowed:
        d = by_id[k]
        if per_doc.get(d["doc_id"], 0) >= PER_DOC:
            continue
        per_doc[d["doc_id"]] = per_doc.get(d["doc_id"], 0) + 1
        picked.append(k)
        if len(picked) >= TOP_K:
            break
    evidence = []
    for k in picked:
        d, f = by_id[k], fused[k]
        why = []
        for name, label in (("vector", "meaning match"), ("keyword", "keyword match"), ("entity", "mentions a named entity")):
            if name in f["ranks"]:
                rank, score = f["ranks"][name]
                why.append(f"{label}: rank {rank} (score {score})")
        cid = f"C{cid_start + len(evidence)}"
        text = d["text"] if len(d["text"]) <= 1500 else d["text"][:1500] + " ..."
        evidence.append(dict(cid=cid, kind="document", title=d["title"], section=d["section"], source_path=d["path"],
                             raw_path=d["raw_path"], doc_id=d["doc_id"], chunk_id=k, iq=d["iq"], format=d["format"],
                             classification=d["classification"], accounts=d["accounts"], text=text,
                             score=round(f["rrf"], 4), why=why))
        step.items.append(dict(evidence=cid, document=d["title"], section=d["section"], iq=d["iq"],
                               fused_score=round(f["rrf"], 4), why="; ".join(why)))
    step.data = dict(lucene=q, candidates=len(cand), allowed=len(allowed), denied=len(denied),
                     searched={k: len(v) for k, v in lists.items()})
    step.summary = (f"{len(evidence)} passage(s) from {len(per_doc)} document(s); searched "
                    + ", ".join(f"{k} {len(v)}" for k, v in lists.items()) + f"; {len(denied)} blocked by permissions")
    return evidence
