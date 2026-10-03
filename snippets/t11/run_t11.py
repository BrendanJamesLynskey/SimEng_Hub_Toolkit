"""Deck 11's measurements: profiles, cache simulation, benchmark statistics and the USE checks.

Run on an otherwise idle machine (timings are the point):

    python run_t11.py OUTDIR       # writes OUTDIR/*.folded, *.svg, results.json

Needs: py-spy, valgrind (cachegrind), the disagg-sim and memsim packages, and a release
build of Rust_DES_Kernel's disagg-rs.
"""

from __future__ import annotations

import json
import os
import random
import re
import shutil
import statistics as st
import subprocess
import sys
import time
from collections import Counter
from pathlib import Path

SANDBOX = Path(__file__).resolve().parents[3]
RUST = SANDBOX / "Rust_DES_Kernel" / "target" / "release" / "disagg-rs"
PY = sys.executable
OUT = Path(sys.argv[1] if len(sys.argv) > 1 else "t11_out")
OUT.mkdir(parents=True, exist_ok=True)
R: dict = {"cpu": None, "python": sys.version.split()[0]}
DISAGG = [PY, "-m", "disagg_sim", "--requests", "3000", "--rate", "4", "--seed", "1"]
MEMSIM = [PY, "-c", "from memsim import hbm2e_pc, random_uniform, simulate; t = hbm2e_pc(channels=1); "
                    "print(simulate(t, random_uniform(t, 20000, 1 << 30, seed=3)).efficiency())"]


def run(cmd, **kw):
    return subprocess.run(cmd, capture_output=True, text=True, **kw)


def lscpu():
    out = run(["lscpu"]).stdout
    return re.search(r"Model name:\s*(.*)", out)[1].strip()


# ── 1. perf, as an unprivileged user ─────────────────────────────────────
def perf_check():
    p = run(["perf", "stat", "-e", "cycles,instructions", "--", "true"])
    para = Path("/proc/sys/kernel/perf_event_paranoid").read_text().strip()
    first = next((ln for ln in p.stderr.splitlines() if "paranoid" in ln.lower()), p.stderr.strip()[:200])
    R["perf"] = {"paranoid": para, "exit": p.returncode, "message": first}


# ── 2. py-spy profiles ───────────────────────────────────────────────────
def folded_tables(path: Path, top=10):
    """Self time (leaf frame) and total time (anywhere on the stack) per function, from py-spy's raw output."""
    self_t, total_t, n = Counter(), Counter(), 0
    for line in path.read_text().splitlines():
        stack, _, count = line.rpartition(" ")
        c = int(count)
        frames = [re.sub(r" \((.*?):\d+\)$", r" (\1)", f) for f in stack.split(";")]
        n += c
        self_t[frames[-1]] += c
        for f in set(frames):
            total_t[f] += c
    fmt = lambda f: re.sub(r"\(.*?/(site-packages|src)/", "(", f)  # noqa: E731
    return {"samples": n,
            "self": [(fmt(f), round(100 * c / n, 1)) for f, c in self_t.most_common(top)],
            "total": [(fmt(f), round(100 * c / n, 1)) for f, c in total_t.most_common(top + 15)
                      if "<module>" not in f and "_run_code" not in f and "_run_module" not in f][:top]}


def pyspy(name, cmd):
    folded, svg = OUT / f"{name}.folded", OUT / f"{name}.svg"
    t0 = time.perf_counter()
    run(["py-spy", "record", "-r", "500", "-f", "raw", "-o", str(folded), "--", *cmd])
    wall = time.perf_counter() - t0
    run(["py-spy", "record", "-r", "500", "-f", "flamegraph", "-o", str(svg), "--", *cmd])
    R[f"pyspy_{name}"] = {"cmd": " ".join(c if " " not in c else "'...'" for c in cmd), "wall_s": round(wall, 2),
                          **folded_tables(folded)}


# ── 3. cachegrind ────────────────────────────────────────────────────────
def cachegrind(name, cmd):
    out = OUT / f"cachegrind.{name}.out"
    p = run(["valgrind", "--tool=cachegrind", "--cache-sim=yes", f"--cachegrind-out-file={out}", *cmd])
    d = {}
    for key, pat in [("I_refs", r"I\s+refs:\s+([\d,]+)"), ("I1_miss", r"I1\s+miss rate:\s+([\d.]+)%"),
                     ("D_refs", r"D\s+refs:\s+([\d,]+)"), ("D1_miss", r"D1\s+miss rate:\s+([\d.]+)%"),
                     ("LL_miss", r"LL miss rate:\s+([\d.]+)%"), ("branches", r"Branches:\s+([\d,]+)")]:
        m = re.search(pat, p.stderr)
        d[key] = m[1] if m else None
    ann = run(["cg_annotate", str(out)]).stdout
    rows = []
    take = False
    for ln in ann.splitlines():
        if re.match(r"^-- (File:function|Function:file|Ir.*file:function)", ln) or "file:function" in ln:
            take = True
            continue
        if take and re.match(r"^\s*[\d,]+ \(", ln):
            m = re.match(r"^\s*([\d,]+) \(\s*([\d.]+)%\).*?\s(\S+:\S.*)$", ln)
            if m:
                rows.append((m[3][-90:], m[2]))
            if len(rows) >= 8:
                break
    d["top"] = rows
    R[f"cachegrind_{name}"] = d


# ── 4. benchmark statistics ──────────────────────────────────────────────
def bootstrap_ci(xs, stat=st.median, n=5000, seed=1):
    rnd = random.Random(seed)
    vals = sorted(stat(rnd.choices(xs, k=len(xs))) for _ in range(n))
    return vals[int(0.025 * n)], vals[int(0.975 * n)]


def describe(xs):
    med = st.median(xs)
    mad = st.median(abs(x - med) for x in xs)
    lo, hi = bootstrap_ci(xs)
    return {"n": len(xs), "median": med, "mean": st.mean(xs), "min": min(xs), "max": max(xs),
            "stdev": st.stdev(xs), "cv_pct": 100 * st.stdev(xs) / st.mean(xs), "mad": mad,
            "ci95_median": [lo, hi]}


def gate_false_alarms(xs, k, margin, slowdown=1.0, trials=20000, seed=2):
    """P(gate fires) when comparing the median of k new runs (scaled by slowdown) with the median of k baseline
    runs, both resampled from the same measured runs: an A/A test (slowdown 1) or a known regression."""
    rnd = random.Random(seed)
    fires = 0
    for _ in range(trials):
        base = st.median(rnd.choices(xs, k=k))
        new = slowdown * st.median(rnd.choices(xs, k=k))
        fires += new > base * (1 + margin)
    return fires / trials


def bench():
    # (a) whole-process timings of the Rust CLI, as a CI job would see them
    proc = []
    for _ in range(40):
        t0 = time.perf_counter()
        run([str(RUST), "--n", "3000", "--rate", "4", "--seed", "1"])
        proc.append(time.perf_counter() - t0)
    # (b) in-process repeats of a pure-Python simulation: the first includes imports' and allocators' warm-up
    code = ("import time, json\nfrom memsim import hbm2e_pc, random_uniform, simulate\nt = hbm2e_pc(channels=1)\n"
            "w = random_uniform(t, 6000, 1 << 30, seed=3)\nout = []\n"
            "for _ in range(40):\n    t0 = time.perf_counter(); simulate(t, list(w)); out.append(time.perf_counter() - t0)\n"
            "print(json.dumps(out))")
    inproc = json.loads(run([PY, "-c", code]).stdout)
    R["bench"] = {"rust_process": {"cmd": "disagg-rs --n 3000 --rate 4 --seed 1", "samples": proc, **describe(proc)},
                  "memsim_inprocess": {"cmd": "simulate(hbm2e_pc, 6000 random requests)", "samples": inproc,
                                       **describe(inproc[1:]), "first": inproc[0]}}
    gates = []
    xs = proc
    for k in (1, 3, 5, 10):
        for m in (0.02, 0.05, 0.10):
            gates.append({"k": k, "margin": m, "false_alarm": gate_false_alarms(xs, k, m),
                          "detects_5pct": gate_false_alarms(xs, k, m, slowdown=1.05),
                          "detects_10pct": gate_false_alarms(xs, k, m, slowdown=1.10)})
    R["gates"] = gates


# ── 5. USE: utilisation and saturation of a parallel sweep ──────────────
def use_check():
    rows = []
    for threads in ("1", str(os.cpu_count())):
        env = {**os.environ, "RAYON_NUM_THREADS": threads}
        p = run(["/usr/bin/time", "-v", str(RUST), "--n", "4000", "--seed", "1", "--sweep", "1", "2", "3", "4", "5", "6", "8", "10"],
                env=env)
        g = lambda pat: re.search(pat, p.stderr)[1]  # noqa: E731
        el = g(r"Elapsed \(wall clock\) time.*?: ([\d:.]+)")
        sec = sum(float(x) * 60 ** i for i, x in enumerate(reversed(el.split(":"))))
        cpu = int(g(r"Percent of CPU this job got: (\d+)%"))
        rows.append({"threads": int(threads), "wall_s": sec, "cpu_pct": cpu,
                     "utilisation_pct": round(cpu / os.cpu_count(), 1),
                     "max_rss_mb": round(int(g(r"Maximum resident set size \(kbytes\): (\d+)")) / 1024, 1),
                     "voluntary_cs": int(g(r"Voluntary context switches: (\d+)")),
                     "involuntary_cs": int(g(r"Involuntary context switches: (\d+)"))})
    load = Path("/proc/loadavg").read_text().split()[:3]
    R["use"] = {"runs": rows, "cores": os.cpu_count(), "loadavg_before": load}


if __name__ == "__main__":
    R["cpu"] = lscpu()
    R["loadavg_start"] = Path("/proc/loadavg").read_text().split()[:3]
    assert shutil.which("py-spy") and shutil.which("valgrind") and RUST.exists()
    perf_check()
    pyspy("disagg_sim", DISAGG)
    pyspy("memsim", MEMSIM)
    cachegrind("rust", [str(RUST), "--n", "500", "--rate", "4", "--seed", "1"])
    cachegrind("python", [PY, "-m", "disagg_sim", "--requests", "500", "--rate", "4", "--seed", "1"])
    bench()
    use_check()
    (OUT / "results.json").write_text(json.dumps(R, indent=1))
    print(json.dumps({k: v for k, v in R.items() if k != "bench"}, indent=1)[:4000])
