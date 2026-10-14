"""Entity resolver agent: finds the accounts, deals, programmes, partners and people the question is about."""
import re

from .. import graph
from ..ingest import ALIAS_STOP, ID_RE


_cache = None
GENERIC = {"bank", "health", "healthcare", "insurance", "retail", "logistics", "research", "traders", "manufacturing",
           "airlines", "importers", "house", "coffee", "inc", "the", "and", "data", "platform", "renewal", "program",
           "programme", "store", "fleet", "analytics", "claims", "cloud"}


def invalidate():
    global _cache
    _cache = None


def entity_index(step=None):
    """All named entities from Neo4j (cached until the next ingestion)."""
    global _cache
    if _cache is None:
        rows = graph.run("MATCH (n) WHERE n:Account OR n:Opportunity OR n:Programme OR n:Partner OR n:Contact OR n:Campaign "
                         "OR n:Bid OR n:Project OR n:Contract RETURN labels(n)[0] AS label, n.id AS id, n.name AS name, "
                         "n.account_id AS account_id", step=step, label="Load entity names (cached after first use)")
        _cache = rows
    return _cache


def _aliases(row):
    name = row["name"] or ""
    out = {name}
    words = name.split()
    if row["label"] == "Account" and words:
        if len(words[0]) >= 5 and words[0] not in ALIAS_STOP:
            out.add(words[0])
        elif len(words) > 1:
            out.add(" ".join(words[:2]))
    if row["label"] == "Partner" and name == "AWS":
        out.add("Amazon Web Services")
    return {a for a in out if a}


def resolve(question, ctx, step):
    rows = entity_index(step)
    found, seen = [], set()
    # 1. explicit IDs
    for m in ID_RE.findall(question):
        r = next((r for r in rows if r["id"] == m), None)
        if r and m not in seen:
            seen.add(m)
            found.append(dict(r, matched=m, how="exact ID in question"))
    # 2. names and short names (word-boundary, case-insensitive), longest first so 'Northwind Store Modernisation' beats 'Northwind'
    cands = []
    for r in rows:
        if r["label"] in ("Bid", "Project", "Contract"):
            continue
        for a in _aliases(r):
            if a.lower() in GENERIC or len(a) < 3:
                continue
            if r["label"] == "Contact" and " " not in a:
                continue
            if re.search(r"(?<![\w-])" + re.escape(a) + r"(?![\w-])", question, re.I):
                cands.append((len(a), a, r))
    cands.sort(key=lambda t: -t[0])
    taken_spans = []
    for ln, a, r in cands:
        m = re.search(r"(?<![\w-])" + re.escape(a) + r"(?![\w-])", question, re.I)
        span = (m.start(), m.end())
        overlaps = any(not (span[1] <= s[0] or span[0] >= s[1]) for s in taken_spans)
        if r["id"] in seen:
            continue
        # an alias inside a longer, already-matched name only counts for accounts (e.g. 'Northwind' in a programme name)
        if overlaps and r["label"] != "Account":
            continue
        seen.add(r["id"])
        taken_spans.append(span)
        found.append(dict(r, matched=a, how="name match" if a == r["name"] else f"short name '{a}'"))

    # A user with a full grant on any IQ may look an entity up (each agent still filters by IQ later).
    # A user with only own-scope grants may only use entities tied to their own accounts.
    kept, dropped = [], 0
    for f in found:
        acc = f["account_id"] or (f["id"] if f["label"] == "Account" else None)
        if acc and not ctx["full"] and acc not in ctx["own_accounts"]:
            dropped += 1
            continue
        kept.append(f)
    step.items = [dict(type=f["label"], id=f["id"], name=f["name"], matched=f["matched"], how=f["how"],
                       account=f["account_id"] or "") for f in kept]
    if dropped:
        step.notes.append(f"{dropped} matched entit{'y' if dropped == 1 else 'ies'} outside this user's account scope "
                          "were not used (names withheld).")
    return kept
