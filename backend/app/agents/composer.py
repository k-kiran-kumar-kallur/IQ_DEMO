"""Composer agent: writes the answer from the evidence package only, citing [C#]. Gemini via its OpenAI-compatible API,
or an evidence-only answer when no model is configured."""
import re
import time

from ..db import get_setting

SYSTEM = """You are Enterprise IQ, the assistant for Visionet's sales, delivery, marketing and partner teams.
Answer only from the evidence provided in the user message. Every factual sentence must cite the evidence it comes from
with its ID in square brackets, for example [C2] or [C1][C4]. Never invent numbers, names or dates; copy figures exactly
as they appear in the evidence. If the evidence does not answer the question, say what is missing.
Start with a one- or two-sentence direct answer, then up to six short bullet points with the supporting detail.
Keep it under 250 words. Use plain language; no headings."""


def evidence_block(evidence, limit_chars=24000):
    parts, total = [], 0
    for e in evidence:
        src = e.get("source_path", "")
        head = f"[{e['cid']}] ({e['kind']}) {e['title']}" + (f" - {e['section']}" if e.get("section") else "") + f"\nsource: {src}"
        body = e["text"]
        piece = f"{head}\n{body}"
        if total + len(piece) > limit_chars:
            break
        parts.append(piece)
        total += len(piece)
    return "\n\n".join(parts)


def gemini(question, evidence, step):
    from openai import OpenAI
    key = get_setting("gemini_api_key")
    model = get_setting("gemini_chat_model")
    base = get_setting("gemini_base_url")
    if not key:
        raise RuntimeError("GOOGLE_API_KEY is not set")
    client = OpenAI(api_key=key, base_url=base, timeout=90, max_retries=2)
    user = f"Question: {question}\n\nEvidence:\n{evidence_block(evidence)}"
    t0 = time.perf_counter()
    resp = client.chat.completions.create(model=model, temperature=0.2,
                                          messages=[{"role": "system", "content": SYSTEM}, {"role": "user", "content": user}])
    ms = round((time.perf_counter() - t0) * 1000)
    text = (resp.choices[0].message.content or "").strip()
    # normalise "[C9, C11]" / "[C9; C11]" to "[C9][C11]" so every citation is checkable and clickable
    text = re.sub(r"\[(C\d+(?:\s*[,;]\s*C\d+)+)\]",
                  lambda m: "".join(f"[{c.strip()}]" for c in re.split(r"[,;]", m.group(1))), text)
    usage = getattr(resp, "usage", None)
    info = dict(provider="Gemini (OpenAI-compatible API)", model=model, ms=ms, finish_reason=resp.choices[0].finish_reason,
                input_tokens=getattr(usage, "prompt_tokens", None), output_tokens=getattr(usage, "completion_tokens", None),
                prompt_chars=len(SYSTEM) + len(user))
    step.query("llm", f"system:\n{SYSTEM}\n\nuser:\nQuestion: {question}\n\nEvidence: {len(evidence)} item(s), "
               f"{len(user):,} characters (shown in Sources)", {"model": model, "temperature": 0.2}, 1, ms,
               label=f"Generate answer with {model}")
    return text, info


def extractive(question, evidence):
    if not evidence:
        return "I could not find anything this user is allowed to see that answers the question.", \
               dict(provider="none (evidence only)", model="-", ms=0)
    words = {w.lower() for w in re.findall(r"[A-Za-z]{4,}", question)}
    lines = ["No language model is configured, so this answer is assembled directly from the retrieved evidence."]
    for e in evidence[:8]:
        if e["kind"] == "graph":
            first = e["text"].splitlines()[0]
            lines.append(f"- {first} [{e['cid']}]")
        elif e["kind"] == "fact":
            rows = e["text"].splitlines()
            lines.append(f"- {e['title']}: " + "; ".join(rows[1:3]) + f" [{e['cid']}]")
        else:
            sents = re.split(r"(?<=[.!?])\s+|\n", e["text"])
            best = max(sents, key=lambda s: len(words & {w.lower() for w in re.findall(r"[A-Za-z]{4,}", s)}))
            lines.append(f"- {e['title']}: {best.strip()[:300]} [{e['cid']}]")
    return "\n".join(lines), dict(provider="none (evidence only)", model="-", ms=0)


def compose(question, evidence, step):
    provider = (get_setting("llm_provider") or "gemini").lower()
    if not evidence:
        step.reason = "Nothing was retrieved, so there is nothing to compose from."
        return extractive(question, evidence)
    if provider == "gemini":
        try:
            step.reason = (f"Sends the question plus {len(evidence)} evidence item(s) to the language model with an instruction "
                           "to answer only from that evidence and cite [C#] for every fact.")
            return gemini(question, evidence, step)
        except Exception as ex:
            step.notes.append(f"Gemini call failed ({type(ex).__name__}: {str(ex)[:200]}); fell back to an evidence-only answer.")
    step.reason = step.reason or "No language model configured; the answer lists the strongest evidence directly."
    return extractive(question, evidence)
