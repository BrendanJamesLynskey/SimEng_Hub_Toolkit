"""A small evaluator for a subset of JQL, to run the deck 08 examples against example_project.py's data.

It is a teaching model, not Jira. It implements the semantics documented by Atlassian
(https://support.atlassian.com/jira-software-cloud/docs/use-advanced-search-with-jira-query-language-jql/)
for the subset the deck uses:

* clauses ``field op value`` with =, !=, IN, NOT IN, IS [NOT] EMPTY, ~, >, >=, <, <=;
* ``!=`` and ``NOT IN`` do not match items where the field is empty (as documented:
  write ``(assignee != currentUser() OR assignee IS EMPTY)`` to include them);
* WAS and CHANGED with the predicates FROM, TO, BY, AFTER, BEFORE, ON, DURING, on the fields
  Atlassian allows (assignee, fixVersion, priority, reporter, resolution, status);
* AND, OR, NOT, parentheses, ORDER BY;
* functions currentUser(), openSprints(), closedSprints(), releasedVersions(p),
  unreleasedVersions(p), earliestUnreleasedVersion(p); dates "2026/08/01" and relative "-14d", "-2w".
"""

from __future__ import annotations

import re
from datetime import date, timedelta

TOKEN = re.compile(r'\s*(?:(?P<str>"(?:[^"\\]|\\.)*")|(?P<op>!=|>=|<=|!~|[=~<>(),])|(?P<word>[^\s=!~<>(),"]+))')
HISTORY_FIELDS = {"assignee", "fixversion", "priority", "reporter", "resolution", "status"}
STATUS_CATEGORY = {"To Do": "To Do", "In Progress": "In Progress", "In Review": "In Progress", "Done": "Done"}
ORDER = {"priority": ["Lowest", "Low", "Medium", "High", "Highest"]}


def tokenize(q: str) -> list[str]:
    out, pos = [], 0
    while pos < len(q):
        m = TOKEN.match(q, pos)
        if not m or m.end() == pos:
            if q[pos:].strip():
                raise SyntaxError(f"cannot parse at: {q[pos:]!r}")
            break
        out.append(m[0].strip())
        pos = m.end()
    return out


class Query:
    def __init__(self, text: str, data: dict):
        self.toks, self.i, self.data = tokenize(text), 0, data
        self.now = date.fromisoformat(data["now"])
        self.tree = self.expr()
        self.order = []
        if self.peek_word("ORDER"):
            self.i += 2                                           # ORDER BY
            while True:
                f = self.next()
                d = "ASC"
                if self.peek_word("ASC") or self.peek_word("DESC"):
                    d = self.next().upper()
                self.order.append((f.lower(), d))
                if self.peek() != ",":
                    break
                self.i += 1
        if self.i != len(self.toks):
            raise SyntaxError(f"unexpected {self.toks[self.i]!r}")

    # ── parsing ──────────────────────────────────────────────────────────
    def peek(self):
        return self.toks[self.i] if self.i < len(self.toks) else None

    def peek_word(self, w):
        return (self.peek() or "").upper() == w

    def next(self):
        t = self.peek()
        self.i += 1
        return t

    def expr(self):
        node = self.term()
        while self.peek_word("OR"):
            self.i += 1
            node = ("or", node, self.term())
        return node

    def term(self):
        node = self.factor()
        while self.peek_word("AND"):
            self.i += 1
            node = ("and", node, self.factor())
        return node

    def factor(self):
        if self.peek_word("NOT"):
            self.i += 1
            return ("not", self.factor())
        if self.peek() == "(":
            self.i += 1
            node = self.expr()
            assert self.next() == ")", "missing )"
            return node
        return self.clause()

    def value(self):
        t = self.next()
        if t == "(":                                             # a list
            vals = []
            while self.peek() != ")":
                vals.append(self.value())
                if self.peek() == ",":
                    self.i += 1
            self.i += 1
            return ("list", vals)
        if self.peek() == "(":                                   # a function call
            self.i += 1
            args = []
            while self.peek() != ")":
                args.append(self.next().strip('"'))
                if self.peek() == ",":
                    self.i += 1
            self.i += 1
            return ("fn", t, args)
        return t.strip('"') if t.startswith('"') else t

    def clause(self):
        field = self.next().lower()
        op = self.next().upper()
        if op == "IS":
            neg = self.peek_word("NOT")
            self.i += neg
            assert self.next().upper() in ("EMPTY", "NULL")
            return ("empty", field, neg)
        if op == "NOT" and self.peek_word("IN"):
            self.i += 1
            op = "NOT IN"
        if op == "WAS":
            op = "WAS"
            if self.peek_word("NOT"):
                self.i += 1
                op = "WAS NOT"
            if self.peek_word("IN"):
                self.i += 1
                op += " IN"
        if op in ("WAS", "WAS NOT", "WAS IN", "WAS NOT IN", "CHANGED") and field not in HISTORY_FIELDS:
            raise SyntaxError(f"{op} is not supported for {field}")
        val = None if op == "CHANGED" else self.value()
        preds = {}
        while self.peek_word("FROM") or self.peek_word("TO") or self.peek_word("BY") or self.peek_word("AFTER") \
                or self.peek_word("BEFORE") or self.peek_word("ON") or self.peek_word("DURING"):
            k = self.next().upper()                               # (the key first: a[k()] = v() runs v first)
            preds[k] = self.value()
        return ("cmp", field, op, val, preds)

    # ── evaluation ───────────────────────────────────────────────────────
    def date(self, v) -> date:
        if isinstance(v, tuple) and v[0] == "fn" and v[1].lower() == "now":
            return self.now
        m = re.fullmatch(r"(-?\d+)([dw])", v)
        if m:
            return self.now + timedelta(days=int(m[1]) * (7 if m[2] == "w" else 1))
        return date.fromisoformat(v.replace("/", "-"))

    def resolve(self, v, field):
        """A value, list or function call -> a set of comparable strings."""
        if isinstance(v, tuple) and v[0] == "list":
            return set().union(*(self.resolve(x, field) for x in v[1]))
        if isinstance(v, tuple) and v[0] == "fn":
            name = v[1].lower()
            if name == "currentuser":
                return {self.data["currentUser"]}
            if name in ("opensprints", "closedsprints"):
                want = "active" if name == "opensprints" else "closed"
                return {str(s["id"]) for s in self.data["sprints"] if s["state"] == want}
            vs = self.data["versions"]
            if name == "releasedversions":
                return {x["name"] for x in vs if x["released"]}
            if name == "unreleasedversions":
                return {x["name"] for x in vs if not x["released"]}
            if name == "earliestunreleasedversion":
                return {min((x for x in vs if not x["released"]), key=lambda x: x["releaseDate"])["name"]}
            raise SyntaxError(f"unsupported function {v[1]}")
        return {str(v)}

    def get(self, it, field):
        f = {"type": "type", "issuetype": "type", "worktype": "type", "fixversion": "fixVersion", "key": "key",
             "issuekey": "key", "statuscategory": "statusCategory", "project": "project"}.get(field, field)
        if f == "statusCategory":
            return STATUS_CATEGORY[it["status"]]
        if f == "project":
            return it["key"].split("-")[0]
        return it.get(f)

    def history_values(self, it, field, preds):
        """(value, from, to) intervals for WAS: each value the field held and when."""
        name = {"fixversion": "fixVersion"}.get(field, field)
        changes = [h for h in it["history"] if h["field"] == name]
        first = changes[0]["from"] if changes else it.get(name)
        spans, start = [], date.fromisoformat(it["created"])
        cur = first
        for h in changes:
            d = date.fromisoformat(h["on"])
            spans.append((cur, start, d, h["by"]))
            cur, start = h["to"], d
        spans.append((cur, start, self.now + timedelta(days=1), None))
        return spans

    def window_ok(self, a, b, preds):
        """Does the interval [a, b) satisfy AFTER/BEFORE/ON/DURING?"""
        if "AFTER" in preds and b <= self.date(preds["AFTER"]):
            return False
        if "BEFORE" in preds and a >= self.date(preds["BEFORE"]):
            return False
        if "ON" in preds:
            d = self.date(preds["ON"])
            if not (a <= d < b):
                return False
        if "DURING" in preds:
            d1, d2 = (self.date(x) for x in preds["DURING"][1])
            if b <= d1 or a > d2:
                return False
        return True

    def match(self, node, it) -> bool:
        kind = node[0]
        if kind == "and":
            return self.match(node[1], it) and self.match(node[2], it)
        if kind == "or":
            return self.match(node[1], it) or self.match(node[2], it)
        if kind == "not":
            return not self.match(node[1], it)
        if kind == "empty":
            v = self.get(it, node[1])
            empty = v is None or v == []
            return not empty if node[2] else empty
        _, field, op, val, preds = node
        if op == "CHANGED":
            name = {"fixversion": "fixVersion"}.get(field, field)
            for h in it["history"]:
                if h["field"] != name:
                    continue
                d = date.fromisoformat(h["on"])
                if "FROM" in preds and h["from"] not in self.resolve(preds["FROM"], field):
                    continue
                if "TO" in preds and h["to"] not in self.resolve(preds["TO"], field):
                    continue
                if "BY" in preds and h["by"] not in self.resolve(preds["BY"], field):
                    continue
                if self.window_ok(d, d + timedelta(days=1), preds):
                    return True
            return False
        if op.startswith("WAS"):
            want = self.resolve(val, field)
            held = {v for v, a, b, by in self.history_values(it, field, preds)
                    if self.window_ok(a, b, preds) and ("BY" not in preds or by in self.resolve(preds["BY"], field))}
            return bool(held & want) if op in ("WAS", "WAS IN") else not (held & want)
        cur = self.get(it, field)
        if cur is None or cur == []:
            return False                                          # documented: != and NOT IN skip empty fields
        if field in ("created", "updated", "resolved", "due"):
            c, d = date.fromisoformat(cur), self.date(val)
            return {"=": c == d, "!=": c != d, ">": c > d, ">=": c >= d, "<": c < d, "<=": c <= d}[op]
        if op == "~":                                             # words and simple derivatives ("win" finds "wins")
            words = re.findall(r"\w+", str(cur).lower())
            return all(any(t.startswith(w) for t in words) for w in re.findall(r"\w+", val.lower()))
        if op in (">", ">=", "<", "<=") and field in ORDER:
            r, o = ORDER[field].index(cur), ORDER[field].index(val)
            return {">": r > o, ">=": r >= o, "<": r < o, "<=": r <= o}[op]
        have = {str(x) for x in cur} if isinstance(cur, list) else {str(cur)}
        want = self.resolve(val, field)
        return {"=": bool(have & want), "IN": bool(have & want), "!=": not (have & want),
                "NOT IN": not (have & want)}[op]

    def run(self) -> list[dict]:
        out = [it for it in self.data["issues"] if self.match(self.tree, it)]
        for f, d in reversed(self.order):
            def key(it, f=f):
                v = self.get(it, f)
                return ORDER[f].index(v) if f in ORDER and v in ORDER[f] else (v is None, v or "")
            out.sort(key=key, reverse=(d == "DESC"))
        return out


def search(q: str, data: dict) -> list[str]:
    return [it["key"] for it in Query(q, data).run()]
