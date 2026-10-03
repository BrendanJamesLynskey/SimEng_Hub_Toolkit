"""An EXAMPLE issue log for deck 08: a fictional simulator team, generated from a fixed seed.

This is not data from any real Jira site. It exists so that the deck's JQL examples can be
run (by jql.py, a small evaluator for a subset of JQL) and its metrics computed from a
workflow history, instead of being shown as screenshots or invented numbers.

    python example_project.py      # writes issues.json and prints the metrics
"""

from __future__ import annotations

import json
import random
from datetime import date, timedelta
from pathlib import Path

START, NOW = date(2026, 7, 6), date(2026, 9, 28)        # twelve weeks; "now" is fixed
WORKFLOW = ["To Do", "In Progress", "In Review", "Done"]
VERSIONS = [("1.4", date(2026, 8, 3), True), ("1.5", date(2026, 9, 14), True), ("1.6", date(2026, 10, 26), False),
            ("1.7", date(2026, 12, 7), False)]
SPRINTS = [(n, START + timedelta(days=14 * (n - 1)), START + timedelta(days=14 * n)) for n in range(1, 8)]
PEOPLE = ["alex", "sam", "jo", "ri"]
EPICS = [("Memory model v2", "memsim"), ("PyTorch front end", "frontend"), ("Nightly regression", "ci"),
         ("Power model calibration", "power")]
STORIES = {
    "memsim": ["Add bank-group timing", "FR-FCFS scheduler", "Refresh model", "Cross-check against DRAMsim3",
               "XOR address mapping", "Protocol checker"],
    "frontend": ["Dispatch trace on meta device", "ONNX graph walk", "torch.compile backend", "Operator coverage report",
                 "Fused attention cost rule", "Decode step tracing"],
    "ci": ["Jenkins pipeline for memsim", "JUnit and coverage publishing", "Performance gate", "Nightly sweep",
           "Traceability matrix in CI"],
    "power": ["Idle power from measurements", "Energy per FLOP fit", "DVFS validation", "Power-cap scenarios"],
}
BACKLOG = [("HBM3 preset", "memsim"), ("Multi-device traces", "frontend"), ("Rust core for the memory model", "memsim"),
           ("Dashboard for simulator metrics", "ci"), ("Thermal throttling model", "power")]
BUGS = ["Wrong row-hit latency under refresh", "ONNX shapes missing for attention", "Gate flaky on loaded agent",
        "Decode FLOPs off by one token", "Embedding table counted per step", "Sweep CSV has duplicate rows",
        "Coverage report crashes on empty trace", "tFAW not enforced across ranks"]


def generate(seed: int = 7) -> dict:
    rnd = random.Random(seed)
    issues, n = [], 0

    def new(**kw):
        nonlocal n
        n += 1
        kw["key"] = f"SIM-{n}"
        issues.append(kw)
        return kw

    epics = [new(type="Epic", summary=s, component=c, parent=None) for s, c in EPICS]
    for e in epics:
        for s in STORIES[e["component"]]:
            new(type=rnd.choice(["Story", "Story", "Task"]), summary=s, component=e["component"], parent=e["key"])
    for b, c in BACKLOG:                                       # not started yet
        new(type="Story", summary=b, component=c, parent=next(e["key"] for e in epics if e["component"] == c),
            backlog=True)
    for b in BUGS:
        c = rnd.choice(list(STORIES))
        new(type="Bug", summary=b, component=c, parent=next(e["key"] for e in epics if e["component"] == c))

    for it in issues:
        lo = 35 if it["type"] == "Bug" else 0                    # bugs arrive once there is code to break
        created = START + timedelta(days=rnd.randint(lo, 80) if it["type"] != "Epic" else 0)
        it.update(created=created.isoformat(), assignee=rnd.choice(PEOPLE), reporter=rnd.choice(PEOPLE),
                  priority=rnd.choice(["Medium", "Medium", "High", "Low"] + (["Highest"] if it["type"] == "Bug" else [])),
                  labels=sorted(set(rnd.sample(["validation", "perf", "regression", "docs", "tech-debt"],
                                               rnd.choice([0, 1, 1, 2]))) | ({"regression"} if it["type"] == "Bug" and
                                                                             rnd.random() < 0.5 else set())),
                  points=rnd.choice([1, 2, 3, 5, 8]) if it["type"] in ("Story", "Task") else None)
        # walk the workflow: each step takes a few days; some items are still in flight at NOW
        hist, t, status = [], created, "To Do"
        # most items run to Done (or are still moving at NOW); about 1 in 6 stalls part-way
        target = rnd.choices([1, 2, 3], weights=[1, 1, 10])[0] if it["type"] != "Epic" else 0
        if it.pop("backlog", False):
            target = 0
        for nxt in WORKFLOW[1:target + 1]:
            t = t + timedelta(days=rnd.randint(1, 4) if nxt == "In Progress" else rnd.randint(1, 8))
            if t > NOW:
                break
            if nxt == "Done" and rnd.random() < 0.15:          # sent back from review once
                back = t
                hist.append({"field": "status", "from": "In Review", "to": "In Progress", "on": back.isoformat(),
                             "by": it["assignee"]})
                t = t + timedelta(days=rnd.randint(1, 4))
                if t > NOW:
                    status = "In Progress"
                    break
                hist.append({"field": "status", "from": "In Progress", "to": "In Review", "on": t.isoformat(),
                             "by": it["assignee"]})
                t = t + timedelta(days=rnd.randint(1, 3))
                if t > NOW:
                    status = "In Review"
                    break
            hist.append({"field": "status", "from": status, "to": nxt, "on": t.isoformat(), "by": it["assignee"]})
            status = nxt
        if rnd.random() < 0.2 and it["type"] != "Epic":         # some reassignments
            new_a = rnd.choice([p for p in PEOPLE if p != it["assignee"]])
            hist.append({"field": "assignee", "from": it["assignee"], "to": new_a,
                         "on": (created + timedelta(days=1)).isoformat(), "by": it["reporter"]})
            it["assignee"] = new_a
        hist.sort(key=lambda h: h["on"])
        it["status"], it["history"] = status, hist
        if status == "To Do" and it["type"] != "Epic" and rnd.random() < 0.6:   # not started: often unassigned
            it["assignee"] = None
        it["resolution"] = "Done" if status == "Done" else None
        it["resolved"] = next((h["on"] for h in reversed(hist) if h["to"] == "Done"), None)
        # versions and sprints
        ref = date.fromisoformat(it["resolved"]) if it["resolved"] else NOW + timedelta(days=rnd.randint(5, 60))
        it["fixVersion"] = next((v for v, d, _ in VERSIONS if ref <= d), "1.7") if it["type"] != "Epic" else None
        if it["type"] == "Bug" and not it["resolved"]:
            it["fixVersion"] = "1.6"                              # open bugs are targeted at the next release
        sp = [s for s, a, b in SPRINTS if a <= ref < b] or ([7] if it["type"] != "Epic" and status != "To Do" else [])
        it["sprint"] = sp[0] if sp and it["type"] != "Epic" else None
    active = [i["assignee"] for i in issues if i.get("sprint") == 7 and i["assignee"]]
    me = max(sorted(set(active)), key=active.count)               # "current user": most current-sprint work
    return {"note": "Example data generated by example_project.py (seed 7). Not from any real Jira site.",
            "now": NOW.isoformat(), "currentUser": me,
            "versions": [{"name": v, "releaseDate": d.isoformat(), "released": r} for v, d, r in VERSIONS],
            "sprints": [{"id": s, "start": a.isoformat(), "end": b.isoformat(),
                         "state": "closed" if b <= NOW else ("active" if a <= NOW else "future")} for s, a, b in SPRINTS],
            "issues": issues}


def flow_metrics(data: dict) -> dict:
    """Cycle time (first In Progress -> Done), throughput per week, average WIP, and Little's law."""
    now = date.fromisoformat(data["now"])
    work = [i for i in data["issues"] if i["type"] != "Epic"]
    cycles = []
    for i in work:
        start = next((date.fromisoformat(h["on"]) for h in i["history"] if h["to"] == "In Progress"), None)
        if i["resolved"] and start:
            cycles.append((date.fromisoformat(i["resolved"]) - start).days)
    cycles.sort()

    def pct(p):
        return cycles[min(len(cycles) - 1, int(p / 100 * len(cycles)))]
    start = date.fromisoformat(min(i["created"] for i in work))
    days = (now - start).days
    wip_days = 0                                    # item-days spent between In Progress and Done
    for i in work:
        s = next((date.fromisoformat(h["on"]) for h in i["history"] if h["to"] == "In Progress"), None)
        if s:
            e = date.fromisoformat(i["resolved"]) if i["resolved"] else now
            wip_days += (e - s).days
    done = sum(1 for i in work if i["resolved"])
    thr = done / days
    ages = []                                       # in flight now: days since first In Progress
    for i in work:
        s = next((date.fromisoformat(h["on"]) for h in i["history"] if h["to"] == "In Progress"), None)
        if s and not i["resolved"]:
            ages.append(((now - s).days, i["key"]))
    p85 = pct(85)
    aged = sorted((a, k) for a, k in ages if a > p85)
    return {"items": len(work), "done": done, "cycle_p50": pct(50), "cycle_p85": pct(85),
            "cycle_mean": round(sum(cycles) / len(cycles), 2), "throughput_per_week": round(7 * thr, 2),
            "avg_wip": round(wip_days / days, 2), "little_wip": round(thr * sum(cycles) / len(cycles), 2),
            "days": days, "in_flight": len(ages), "aged": [k for _, k in aged], "aged_mean_age": round(
                sum(a for a, _ in aged) / len(aged), 1) if aged else 0,
            "wip_days_finished": sum(cycles), "wip_days_in_flight": sum(a for a, _ in ages)}


if __name__ == "__main__":
    d = generate()
    Path(__file__).with_name("issues.json").write_text(json.dumps(d, indent=1) + "\n")
    print(json.dumps(flow_metrics(d), indent=1))
