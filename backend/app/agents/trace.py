"""Trace recorder: every agent writes one step with what it did, why, the exact queries it ran and what came back."""
import time


class Step:
    def __init__(self, trace, agent, title):
        self.trace, self.agent, self.title = trace, agent, title
        self.status = "ran"
        self.reason = ""
        self.summary = ""
        self.queries = []
        self.items = []          # structured outputs shown as a table in the UI
        self.notes = []          # permission decisions, fallbacks, warnings
        self.data = {}           # free-form extras (e.g. subgraph for drawing)
        self.t0 = time.perf_counter()
        self.start_ms = round((self.t0 - trace.t0) * 1000)
        self.ms = 0

    def query(self, lang, text, params, rows, ms, label=None, sample=None):
        self.queries.append(dict(lang=lang, label=label or "", text=text, params=params or {}, rows=rows, ms=ms,
                                 sample=sample or []))

    def to_dict(self):
        return dict(agent=self.agent, title=self.title, status=self.status, reason=self.reason, summary=self.summary,
                    queries=self.queries, items=self.items, notes=self.notes, data=self.data, start_ms=self.start_ms,
                    ms=self.ms)


class Trace:
    def __init__(self, question, user):
        self.question, self.user = question, user
        self.t0 = time.perf_counter()
        self.steps = []

    def step(self, agent, title):
        s = Step(self, agent, title)
        self.steps.append(s)
        return s

    def end(self, s):
        s.ms = round((time.perf_counter() - s.t0) * 1000)

    def skip(self, agent, title, reason):
        s = self.step(agent, title)
        s.status, s.reason, s.summary = "skipped", reason, "Not run"
        return s

    def total_ms(self):
        return round((time.perf_counter() - self.t0) * 1000)

    def to_list(self):
        return [s.to_dict() for s in self.steps]
