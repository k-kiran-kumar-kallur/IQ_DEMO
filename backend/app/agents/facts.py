"""Facts agent: read-only SQL over the SQLite fact tables loaded from the Excel/CSV trackers."""
import time

from .. import db
from ..ingest import CANON
from ..permissions import IQS
from .router import INTENTS


def _fmt(v):
    if v is None:
        return ""
    if isinstance(v, (int, float)) and not isinstance(v, bool) and abs(v) >= 10000:
        return f"{v:,.0f}"
    if isinstance(v, float):
        return f"{v:.3f}".rstrip("0").rstrip(".")
    return str(v)


def _in(col, ids):
    return f"{col} IN ({','.join('?' * len(ids))})", list(ids)


def templates(intent, accounts, names, ctx, question, partners=None):
    """Return a list of (title, view, sql, params, row_level). `accounts` = account IDs in scope, `names` = their names."""
    q = question.lower()
    out = []
    acc_where, acc_params = _in("account_id", accounts) if accounts else ("1=1", [])
    name_where, name_params = _in("account", names) if names else ("1=1", [])
    if intent == "revenue":
        margin = ", ROUND(SUM(revenue_usd * gross_margin) / SUM(revenue_usd), 3) AS gross_margin" if ctx["see_margin"] else ""
        if accounts:
            out.append(("Revenue by year for the account(s) in scope", "v_revenue",
                        f"SELECT account, year, ROUND(SUM(revenue_usd)) AS revenue_usd{margin} FROM v_revenue "
                        f"WHERE {acc_where} GROUP BY account, year ORDER BY account, year", acc_params, True))
        else:
            out.append(("Total revenue by year", "v_revenue",
                        f"SELECT year, ROUND(SUM(revenue_usd)) AS revenue_usd{margin} FROM v_revenue GROUP BY year ORDER BY year",
                        [], False))
            out.append(("Top accounts by 2026 revenue", "v_revenue",
                        "SELECT account, ROUND(SUM(revenue_usd)) AS revenue_2026_usd FROM v_revenue WHERE year = 2026 "
                        "GROUP BY account ORDER BY 2 DESC LIMIT 6", [], True))
    elif intent == "pipeline":
        if "stall" in q:
            out.append(("Stalled deals (no activity for more than 45 days)", "v_pipeline",
                        f"SELECT opp_id, account, opportunity, stage, tcv_usd, days_since_activity, owner FROM v_pipeline "
                        f"WHERE stalled_flag = 'STALLED' AND {acc_where}", acc_params, True))
        if accounts:
            out.append(("Open opportunities for the account(s) in scope", "v_pipeline",
                        f"SELECT opp_id, account, opportunity, stage, tcv_usd, probability, close_date, notes FROM v_pipeline "
                        f"WHERE {acc_where} ORDER BY tcv_usd DESC", acc_params, True))
        else:
            out.append(("Open pipeline by stage", "v_pipeline",
                        "SELECT stage, COUNT(*) AS deals, SUM(tcv_usd) AS tcv_usd, ROUND(SUM(weighted_usd)) AS weighted_usd "
                        "FROM v_pipeline GROUP BY stage ORDER BY stage", [], False))
    elif intent == "renewals":
        out.append(("Renewals due in the next 180 days (in scope)", "v_renewals",
                    f"SELECT contract, account, service, acv_usd, contract_end, days_to_end, risk, notes FROM v_renewals "
                    f"WHERE {acc_where} ORDER BY contract_end", acc_params, True))
    elif intent == "bids":
        if "win rate" in q or not names:
            out.append(("Win rate on decided bids", "v_bids",
                        "SELECT CASE WHEN bid_type IN ('RFP','RFI') THEN 'Competitive (RFP/RFI)' ELSE 'Renewal / proactive' END "
                        "AS bid_group, SUM(status='Won') AS won, SUM(status='Lost') AS lost, "
                        "ROUND(1.0 * SUM(status='Won') / SUM(status IN ('Won','Lost')), 3) AS win_rate "
                        "FROM v_bids WHERE status IN ('Won','Lost') GROUP BY bid_group", [], False))
        if names:
            out.append(("Bids for the account(s) in scope", "v_bids",
                        f"SELECT bid_id, account, bid_type, deal_value_usd, submission_date, decision_date, status, "
                        f"win_loss_no_bid_reason, competitors FROM v_bids WHERE {name_where} ORDER BY rfx_received DESC",
                        name_params, True))
        else:
            out.append(("Bids in flight", "v_bids",
                        "SELECT bid_id, account, bid_type, deal_value_usd, submission_date, decision_date, status FROM v_bids "
                        "WHERE status NOT IN ('Won','Lost','No-bid') ORDER BY submission_date", [], True))
    elif intent == "funding":
        where, params = (_in("partner", partners) if partners else (name_where, name_params))
        out.append(("Partner funding (approved, used, available, expiry)", "v_funding",
                    f"SELECT funding_id, partner, programme, account, opp_id, approved_usd, used_usd, available_usd, expires, "
                    f"days_to_expiry, expiry_alert, status FROM v_funding WHERE {where} ORDER BY expires", params, True))
    elif intent == "registrations":
        where, params = (_in("partner", partners) if partners else (acc_where, acc_params))
        out.append(("Deal registrations", "v_registrations",
                    f"SELECT registration_id, partner, account, opp_id, status, expires, days_to_expiry, alert FROM v_registrations "
                    f"WHERE {where} ORDER BY expires", params, True))
    elif intent == "health":
        out.append(("Account health scorecard (Sep 2026)", "v_health",
                    f"SELECT account_name AS account, csat_q3, csat_q2, open_escalations, sla_attainment_pct, delivery_rag, "
                    f"health_score_0_100 AS health_score, health_status, notes FROM v_health WHERE {acc_where} "
                    f"ORDER BY health_score_0_100", acc_params, True))
    elif intent == "delivery":
        cw, cp = _in("client", names) if names else ("1=1", [])
        out.append(("Projects: progress, cost and RAG (week 40)", "v_projects",
                    f"SELECT project, project_name, client, complete AS pct_complete, budget_burn, eac_cost, eac_variance, "
                    f"projected_margin, forecast_end, rag_w38, rag_w39, rag_w40 FROM v_projects WHERE {cw}", cp, True))
    elif intent == "campaign":
        out.append(("Campaign attribution and ROI", "v_attribution",
                    "SELECT campaign_id, campaign, spend_usd, mqls, sqls, opps_sourced, pipeline_sourced_usd, won_revenue_usd "
                    "FROM v_attribution ORDER BY pipeline_sourced_usd DESC", [], False))
    elif intent == "contacts" and accounts:
        out.append(("Stakeholders at the account(s) in scope", "v_contacts",
                    f"SELECT full_name, job_title, buying_role, relationship_strength, status, notes FROM v_contacts "
                    f"WHERE {acc_where}", acc_params, True))
    return out


def run(intents, entities, ctx, question, step, cid_start):
    accounts = sorted({e["account_id"] or e["id"] for e in entities if (e["account_id"] or e["label"] == "Account")})
    acc_rows = [e for e in entities if e["label"] == "Account"]
    names = sorted({e["name"] for e in acc_rows})
    if not names and accounts:
        cols, rows = db.query(f"SELECT DISTINCT account FROM v_pipeline WHERE account_id IN ({','.join('?' * len(accounts))}) "
                              f"UNION SELECT DISTINCT account FROM v_revenue WHERE account_id IN ({','.join('?' * len(accounts))})",
                              accounts + accounts)
        names = sorted({r[0] for r in rows})
    evidence = []
    for intent in intents:
        iq = INTENTS[intent]["iq"]
        level = ctx["grants"].get(iq)
        scope_acc, scope_names, partners = accounts, names, None
        if level == "own" and iq == "partners" and ctx["partners"]:
            _, rows = db.query(f"SELECT DISTINCT partner FROM v_partner_pipeline WHERE partner_id IN "
                               f"({','.join('?' * len(ctx['partners']))})", ctx["partners"])
            partners = sorted({r[0] for r in rows}) or ["(none)"]
            note = f"{IQS[iq]} is own-scope for this user: SQL filtered to partners {', '.join(partners)}."
            if note not in step.notes:
                step.notes.append(note)
        elif level == "own":
            scope_acc = [a for a in accounts if a in ctx["own_accounts"]] or list(ctx["own_accounts"])
            if not scope_acc:
                step.notes.append(f"{IQS[iq]} is own-scope for this user but no accounts are entitled: no rows returned.")
                continue
            _, rows = db.query(f"SELECT DISTINCT account FROM v_revenue WHERE account_id IN ({','.join('?' * len(scope_acc))}) "
                               f"UNION SELECT DISTINCT account FROM v_pipeline WHERE account_id IN ({','.join('?' * len(scope_acc))})",
                               scope_acc + scope_acc)
            scope_names = sorted({r[0] for r in rows}) or ["(none)"]
            note = f"{IQS[iq]} is own-scope for this user: SQL filtered to accounts {', '.join(scope_acc)}."
            if note not in step.notes:
                step.notes.append(note)
        for title, view, sql, params, row_level in templates(intent, scope_acc, scope_names, ctx, question, partners):
            if level == "aggregate" and row_level:
                step.notes.append(f"Skipped '{title}': {IQS[iq]} is totals-only for this user, and this query returns rows.")
                continue
            t0 = time.perf_counter()
            cols, rows = db.query(sql, params)
            ms = round((time.perf_counter() - t0) * 1000)
            rel, sheet = CANON[view]
            step.query("sql", sql, {"params": params} if params else {}, len(rows), ms, label=f"{title} ({view})",
                       sample=[dict(zip(cols, r)) for r in rows[:5]])
            if not rows:
                continue
            lines = [" | ".join(cols)] + [" | ".join(_fmt(v) for v in r) for r in rows[:15]]
            cid = f"C{cid_start + len(evidence)}"
            evidence.append(dict(cid=cid, kind="fact", title=title, source_path=rel, sheet=sheet, iq=iq,
                                 text="\n".join(lines), rows=len(rows), sql=sql,
                                 why=[f"Router matched {INTENTS[intent]['label']}", f"{len(rows)} row(s) from {view}"]))
            step.items.append(dict(evidence=cid, table=view, source=f"{rel} > {sheet}", rows=len(rows), title=title))
    step.summary = f"{len(evidence)} table result(s) from SQLite" if evidence else "No matching rows"
    return evidence
