"""Router agent: decides which retrieval agents run for this question, and records why (or why not)."""
import re

INTENTS = {
    "revenue": dict(iq="revenue", label="revenue figures",
                    words=["revenue", "billing", "billed", "margin", "year on year", "yoy", "month on month", "income", "earned",
                           "how much did", "sales figures"]),
    "pipeline": dict(iq="revenue", label="pipeline and deals",
                     words=["pipeline", "opportunit", "deal", "stage", "close date", "weighted", "stalled", "forecast",
                            "probability", "at risk"]),
    "renewals": dict(iq="revenue", label="renewals and contracts",
                     words=["renewal", "renew", "contract", "churn", "at risk"]),
    "bids": dict(iq="gtm", label="bids and win rates",
                 words=["bid", "rfp", "rfi", "proposal", "win rate", "win/loss", "won", "lost", "tender", "submission",
                        "orals", "bafo", "no-bid", "competitor"]),
    "funding": dict(iq="partners", label="partner funding",
                    words=["funding", "ecif", "mdf", "incentive", "credits", "migrate & modernize", "azure innovate", "expir",
                           "amm"]),
    "registrations": dict(iq="partners", label="deal registrations",
                          words=["registration", "referral", "co-sell", "cosell", "ace "]),
    "health": dict(iq="accounts", label="account health",
                   words=["health", "csat", "satisfaction", "escalation", "sla", "nps", "pulse", "red account"]),
    "delivery": dict(iq="delivery", label="projects and delivery status",
                     words=["project", "programme", "program", "status", "rag", "eac", "budget", "milestone", "delivery",
                            "atlas", "wave", "overrun"]),
    "campaign": dict(iq="campaign", label="campaigns and leads",
                     words=["campaign", "mql", "sql", "lead", "marketing", "webinar", "attribution", "roi", "spend"]),
    "contacts": dict(iq="accounts", label="stakeholders",
                     words=["who ", "stakeholder", "decision maker", "sponsor", "cio", "cfo", "cto", "cdo", "vp ", "contact",
                            "champion", "buyer"]),
}


def detect_intents(question):
    q = " " + question.lower() + " "
    hits = {}
    for key, spec in INTENTS.items():
        words = [w for w in spec["words"] if (re.search(r"\b" + re.escape(w.strip()) + r"\b", q) if len(w.strip()) <= 4 else w in q)]
        if words:
            hits[key] = words
    return hits


def plan(question, entities, ctx, step):
    intents = detect_intents(question)
    decisions = []
    has_any = bool(ctx["full"] or ctx["own"] or ctx["aggregate"])

    if not has_any:
        for agent in ("Graph agent", "Document agent", "Facts agent"):
            decisions.append(dict(agent=agent, run=False, reason=f"{ctx['name']} has no IQ grants (platform role): no business data."))
        step.items = decisions
        step.summary = "Nothing to retrieve for this user"
        return decisions, intents

    if entities:
        names = ", ".join(f"{e['name']} ({e['id']})" for e in entities[:4])
        decisions.append(dict(agent="Graph agent", run=True,
                              reason=f"The question names {names}. A graph walk from these nodes collects what is connected to "
                                     "them: deals, bids, contracts, programmes, people, partners and funding."))
    else:
        decisions.append(dict(agent="Graph agent", run=False,
                              reason="No account, deal, programme, partner or person was named, so there is no node to start "
                                     "a graph walk from."))

    decisions.append(dict(agent="Document agent", run=True,
                          reason="Narrative evidence (why something happened, what people said, plans and decisions) lives in "
                                 "documents, so hybrid vector + keyword search runs for every question"
                                 + (", boosted towards chunks that mention the named entities." if entities else ".")))

    usable = {k: v for k, v in intents.items() if INTENTS[k]["iq"] in ctx["grants"]}
    blocked = {k: v for k, v in intents.items() if k not in usable}
    if usable:
        parts = [f"{INTENTS[k]['label']} (matched: {', '.join(repr(w.strip()) for w in v[:3])})" for k, v in usable.items()]
        decisions.append(dict(agent="Facts agent", run=True,
                              reason="The question asks about " + "; ".join(parts) +
                                     ". Exact numbers come from the SQLite fact tables, not from document text.",
                              intents=list(usable)))
    else:
        why = "No numeric or tracker keywords (revenue, pipeline, renewal, bid, funding, health, project, campaign)."
        if blocked:
            why = ("Matched " + ", ".join(INTENTS[k]["label"] for k in blocked) +
                   ", but this user has no grant on the IQ that owns those tables.")
        decisions.append(dict(agent="Facts agent", run=False, reason=why))
    step.items = decisions
    ran = [d["agent"] for d in decisions if d["run"]]
    step.summary = f"Run {', '.join(ran)}" if ran else "No retrieval"
    return decisions, intents
