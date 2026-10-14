"""Roles and access. A role sets the access level per IQ; each user's own entitlements (accounts, partners) set the scope
for 'own' levels. Users and their entitlements live in SQLite (see auth.py); role definitions live here.
Levels: full (read/write), own (limited to the user's accounts), aggregate (totals only), absent = no access."""

IQS = {"gtm": "GTM IQ", "campaign": "Campaign IQ", "accounts": "Accounts IQ", "revenue": "Sales (Revenue) IQ",
       "solutions": "Solutions IQ", "partners": "Channels & Partners IQ", "delivery": "Delivery IQ"}

FOLDER_TO_IQ = {"GTM": "gtm", "Campaign": "campaign", "Accounts": "accounts", "Sales_Revenue": "revenue",
                "Solutions": "solutions", "Channels_Partners": "partners", "Delivery": "delivery"}

ALL_FULL = {k: "full" for k in IQS}

ROLES = {
    "executive": dict(name="Executive", grants=ALL_FULL,
                      note="Every IQ, all accounts. Revenue margin is hidden (Finance only)."),
    "gtm_team": dict(name="GTM / Bid Manager",
                     grants=dict(gtm="full", campaign="full", accounts="own", revenue="aggregate", solutions="full",
                                 partners="own"),
                     note="GTM in full, revenue as totals only, accounts and partners limited to the user's pursuit accounts."),
    "marketing": dict(name="Inside Sales & Marketing",
                      grants=dict(gtm="aggregate", campaign="full", accounts="own", solutions="full"),
                      note="Campaign in full, GTM totals only, accounts limited to the user's target accounts."),
    "account_owner": dict(name="Account Owner / Client Partner",
                          grants=dict(gtm="own", campaign="own", accounts="own", revenue="own", solutions="full",
                                      partners="own", delivery="own"),
                          note="Every IQ for the user's own accounts, plus the whole Solutions library (proposals, pricing, case studies)."),
    "sales_ops_finance": dict(name="Sales Ops / Finance",
                              grants=dict(gtm="full", campaign="full", accounts="full", revenue="full", partners="full"),
                              note="Revenue in full including margin; no Solutions or Delivery."),
    "presales": dict(name="Presales / Solutions", grants=dict(gtm="full", accounts="full", solutions="full", delivery="full"),
                     note="Solutions in full plus GTM, Accounts and Delivery."),
    "alliances": dict(name="Alliances / Partner Manager",
                      grants=dict(gtm="own", accounts="own", revenue="aggregate", solutions="full", partners="own"),
                      note="Partners IQ for the user's partners; accounts derived from those partners' deals; revenue totals only."),
    "delivery_lead": dict(name="Delivery Lead", grants=dict(accounts="own", solutions="full", delivery="own"),
                          note="Delivery for the user's programmes and their client accounts."),
    "platform_admin": dict(name="Platform Admin", grants={}, admin=True,
                           note="Manages settings, data loading and users. No business data (separation of duties)."),
}

# Seeded on first start. All demo passwords are Demo@123 (stored only as salted scrypt hashes).
DEMO_USERS = [
    # username, display name, job title, role, own accounts, own partners
    ("laura.chen", "Laura Chen", "Chief Revenue Officer", "executive", [], []),
    ("priya.raman", "Priya Raman", "Client Partner, Retail & Healthcare", "account_owner", ["ACC-1001", "ACC-1002"], []),
    ("marcus.bell", "Marcus Bell", "VP Sales, BFSI", "account_owner", ["ACC-1003", "ACC-1005", "ACC-1013", "ACC-1014"], []),
    ("sophie.turner", "Sophie Turner", "Client Partner, Manufacturing & Logistics", "account_owner",
     ["ACC-1004", "ACC-1006", "ACC-1008"], []),
    ("anita.rao", "Anita Rao", "Bid Manager, GTM", "gtm_team", ["ACC-1003", "ACC-1004", "ACC-1006", "ACC-1013", "ACC-1014"], []),
    ("sarah.kim", "Sarah Kim", "Director, Inside Sales & Marketing", "marketing", ["ACC-1003", "ACC-1005", "ACC-1007"], []),
    ("daniel.cho", "Daniel Cho", "Sales Ops & Finance Manager", "sales_ops_finance", [], []),
    ("ravi.shankar", "Ravi Shankar", "Head of Presales & Solutions", "presales", [], []),
    ("elena.novak", "Elena Novak", "Alliances Director (Microsoft, AWS)", "alliances", [], ["PRT-01", "PRT-02"]),
    ("kevin.shah", "Kevin Shah", "Partner Manager (Databricks, Snowflake, ServiceNow, Guidewire)", "alliances", [],
     ["PRT-03", "PRT-04", "PRT-05", "PRT-06"]),
    ("arjun.mehta", "Arjun Mehta", "Delivery Director", "delivery_lead", ["ACC-1001", "ACC-1008"], []),
    ("admin", "Platform Admin", "Platform Administrator", "platform_admin", [], []),
]


def context(user, partner_accounts=None):
    """Permission context for a logged-in user (dict from the users table)."""
    role = ROLES.get(user["role"], ROLES["platform_admin"])
    grants = role["grants"]
    accounts = list(user.get("accounts") or [])
    if user.get("partners") and partner_accounts:
        accounts = sorted(set(accounts) | set(partner_accounts))
    return dict(
        user=user["username"], name=user["display_name"], role=user["role"], role_name=role["name"], note=role["note"],
        grants=grants,
        full=[k for k, v in grants.items() if v == "full"],
        own=[k for k, v in grants.items() if v == "own"],
        aggregate=[k for k, v in grants.items() if v == "aggregate"],
        none=[k for k in IQS if k not in grants],
        own_accounts=accounts, partners=list(user.get("partners") or []),
        see_margin=user["role"] == "sales_ops_finance",
    )


def chunk_allowed_cypher(alias="c"):
    """Cypher predicate that decides if a chunk may be shown to the user."""
    return (f"({alias}.iq IN $full OR ({alias}.iq IN $own AND "
            f"all(x IN {alias}.accounts WHERE x IN $own_accounts)))")


def document_allowed(ctx, iq, accounts):
    """Whole-document access (used before serving an original file): stricter than chunk access, because a file can
    contain other clients' sections that chunk-level filtering would hide."""
    level = ctx["grants"].get(iq)
    if level == "full":
        return True
    if level == "own":
        return all(a in ctx["own_accounts"] for a in accounts)
    return False
