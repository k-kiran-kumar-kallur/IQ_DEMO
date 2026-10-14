"""Verifier agent: checks that every number in the answer appears in the evidence and every [C#] citation exists."""
import re

NUM = re.compile(r"(?<![\w\[-])\$?\d[\d,]*(?:\.\d+)?\s?(?:%|[MKB]\b|million\b|thousand\b|billion\b)?")


def values(token):
    t = token.strip().lower().replace(" ", "")
    mult = 1.0
    pct = t.endswith("%")
    for suf, m in (("million", 1e6), ("thousand", 1e3), ("billion", 1e9), ("m", 1e6), ("k", 1e3), ("b", 1e9)):
        if t.endswith(suf) and not pct:
            mult = m
            t = t[: -len(suf)]
            break
    t = t.rstrip("%").lstrip("$").replace(",", "")
    try:
        v = float(t) * mult
    except ValueError:
        return set()
    out = {v}
    if pct:
        out.add(v / 100)
    return out


def numbers(text):
    found = []
    for m in NUM.finditer(text):
        tok = m.group(0).strip()
        bare = tok.replace(",", "")
        if re.fullmatch(r"(19|20)\d\d", bare):            # years
            continue
        if re.fullmatch(r"\d", bare):                       # single digits (list counts, weeks)
            continue
        found.append(tok)
    return found


def verify(answer, evidence, step):
    cited = re.findall(r"\[(C\d+)\]", answer)
    valid = {e["cid"] for e in evidence}
    invalid = sorted(set(c for c in cited if c not in valid))
    ev_text = "\n".join(e["text"] + " " + e.get("title", "") for e in evidence)
    ev_vals = set()
    for tok in numbers(ev_text):
        for v in values(tok):
            ev_vals.add(round(v, 6))
    # also accept plain dates and IDs written in evidence
    checked, unsupported = [], []
    for tok in numbers(re.sub(r"\[C\d+\]", "", answer)):
        if re.search(r"\d{4}-\d\d-\d\d", tok):
            continue
        vs = values(tok)
        ok = any(any(abs(v - e) <= max(abs(e) * 0.006, 0.006) for e in ev_vals) for v in vs) or tok in ev_text
        checked.append(dict(value=tok, supported=ok))
        if not ok:
            unsupported.append(tok)
    if not evidence:
        status = "no evidence"
    elif invalid:
        status = "citation error"
    elif not cited and evidence:
        status = "no citations"
    elif unsupported:
        status = "partially verified"
    else:
        status = "verified"
    step.items = checked
    step.reason = ("Checks the answer before it is shown: each figure must appear in the evidence (within rounding) and "
                   "each [C#] must point to a real evidence item.")
    step.summary = (f"{len(checked) - len(unsupported)}/{len(checked)} figures found in evidence; "
                    f"{len(set(cited))} citation(s), {len(invalid)} invalid")
    if unsupported:
        step.notes.append("Not found in evidence: " + ", ".join(unsupported[:10]))
    return dict(status=status, cited=sorted(set(cited), key=lambda c: int(c[1:])), invalid=invalid,
                numbers_checked=len(checked), unsupported=unsupported)
