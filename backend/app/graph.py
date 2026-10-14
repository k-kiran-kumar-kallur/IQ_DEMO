"""Neo4j access. Every query can be recorded on a trace step (text, parameters, timing, row count)."""
import threading
import time

from neo4j import GraphDatabase

from .db import get_setting

_driver = None
_driver_key = None
_lock = threading.Lock()


def _creds():
    return (get_setting("neo4j_uri"), get_setting("neo4j_username"), get_setting("neo4j_password"),
            get_setting("neo4j_database") or None)


def _make_driver(uri, user, pwd):
    """neo4j+s:// verifies TLS against the OS trust store, which python.org builds on macOS leave empty.
    Verify against certifi's Mozilla bundle instead (still full certificate verification)."""
    if "+s://" in uri:
        import certifi
        from neo4j import TrustCustomCAs
        return GraphDatabase.driver(uri.replace("+s://", "://", 1), auth=(user, pwd), encrypted=True,
                                    trusted_certificates=TrustCustomCAs(certifi.where()), max_connection_lifetime=300)
    return GraphDatabase.driver(uri, auth=(user, pwd), max_connection_lifetime=300)


def driver():
    global _driver, _driver_key
    uri, user, pwd, _ = _creds()
    if not uri or not pwd:
        raise RuntimeError("Neo4j is not configured. Add NEO4J_URI, NEO4J_USERNAME and NEO4J_PASSWORD to .env "
                           "or enter them in Settings.")
    key = (uri, user, pwd)
    with _lock:
        if _driver is None or _driver_key != key:
            if _driver is not None:
                _driver.close()
            _driver = _make_driver(uri, user, pwd)
            _driver_key = key
        return _driver


def reset_driver():
    global _driver, _driver_key
    with _lock:
        if _driver is not None:
            _driver.close()
        _driver, _driver_key = None, None


def _safe_params(params):
    out = {}
    for k, v in (params or {}).items():
        if isinstance(v, list) and len(v) > 20 and all(isinstance(x, float) for x in v[:5]):
            out[k] = f"<{len(v)}-dimension query vector>"
        elif isinstance(v, list) and len(v) > 30:
            out[k] = v[:30] + [f"... {len(v) - 30} more"]
        else:
            out[k] = v
    return out


def run(cypher, params=None, step=None, label=None, sample=5):
    """Run a read or write query; returns a list of dicts."""
    db = _creds()[3]
    t0 = time.perf_counter()
    records, summary, _ = driver().execute_query(cypher, params or {}, database_=db)
    rows = [r.data() for r in records]
    ms = round((time.perf_counter() - t0) * 1000)
    if step is not None:
        step.query("cypher", cypher.strip(), _safe_params(params), len(rows), ms, label=label,
                   sample=[_trim(r) for r in rows[:sample]])
    return rows


def run_auto(cypher, params=None):
    """Auto-commit transaction (needed for CALL { } IN TRANSACTIONS)."""
    db = _creds()[3]
    with driver().session(database=db) as s:
        return s.run(cypher, params or {}).consume()


def _trim(row):
    out = {}
    for k, v in row.items():
        if isinstance(v, str) and len(v) > 220:
            out[k] = v[:220] + "..."
        elif isinstance(v, list) and len(v) > 8:
            out[k] = v[:8] + ["..."]
        elif isinstance(v, dict):
            out[k] = {kk: (vv[:120] + "..." if isinstance(vv, str) and len(vv) > 120 else vv) for kk, vv in v.items()
                      if kk != "embedding"}
        else:
            out[k] = v
    return out


def ping():
    t0 = time.perf_counter()
    rows = run("CALL dbms.components() YIELD name, versions, edition RETURN name, versions[0] AS version, edition")
    counts = run("MATCH (n) RETURN count(n) AS nodes")
    return {"ok": True, "ms": round((time.perf_counter() - t0) * 1000), "server": rows[0] if rows else {},
            "nodes": counts[0]["nodes"] if counts else 0}
