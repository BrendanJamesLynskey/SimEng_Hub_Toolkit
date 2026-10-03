"""Deck 12's measurements: what each tool costs, what it reports, and what this machine allows.

Run on an otherwise idle machine, alone (timings are the point):

    source ~/.local/opt/valgrind-deb/env.sh
    python run_t12.py OUTDIR       # writes OUTDIR/results.json and the raw tool outputs

Needs: py-spy, coverage, valgrind (cachegrind), perf, the disagg-sim package and a release
build of Rust_DES_Kernel's disagg-rs. The GPU and RAPL probes record what happens when the
tools are tried here (no NVIDIA GPU; RAPL is root-only); they never invent a reading.
"""

from __future__ import annotations

import io
import json
import pstats
import re
import shutil
import statistics as st
import subprocess
import sys
import time
from pathlib import Path

SANDBOX = Path(__file__).resolve().parents[3]
RUST = SANDBOX / "Rust_DES_Kernel" / "target" / "release" / "disagg-rs"
PY = sys.executable
OUT = Path(sys.argv[1] if len(sys.argv) > 1 else "t12_out")
OUT.mkdir(parents=True, exist_ok=True)
R: dict = {"python": sys.version.split()[0]}
ARGS = ["--requests", "3000", "--rate", "4", "--seed", "1"]
DISAGG = [PY, "-m", "disagg_sim", *ARGS]
BIN = Path(PY).parent
RETRIES: list[str] = []


def run(cmd, **kw):
    return subprocess.run(cmd, capture_output=True, text=True, **kw)


def timed(cmd, n):
    """Wall-clock seconds of n runs of a command (each run must succeed)."""
    xs = []
    while len(xs) < n:
        t = time.perf_counter()
        p = run(cmd)
        dt = time.perf_counter() - t
        if p.returncode and "No child process" in p.stderr:   # py-spy loses a race with the child's exit
            RETRIES.append(" ".join(map(str, cmd[:4])))       # now and then: run it again, and record it
            continue
        if p.returncode:
            raise SystemExit(f"{cmd} failed:\n{p.stderr[-2000:]}")
        xs.append(dt)
    return xs


# ── 1. what a profiler costs: the same simulation under each tool ─────────
def overheads():
    prof = OUT / "disagg.prof"
    cases = [
        ("plain", "no tool", DISAGG, 5),
        ("cprofile", "cProfile (instrumenting every call)", [PY, "-m", "cProfile", "-o", str(prof), "-m", "disagg_sim", *ARGS], 3),
        ("pyspy100", "py-spy record, 100 Hz", [str(BIN / "py-spy"), "record", "-r", "100", "-f", "raw", "-o",
                                               str(OUT / "pyspy100.txt"), "--", *DISAGG], 3),
        ("pyspy500", "py-spy record, 500 Hz", [str(BIN / "py-spy"), "record", "-r", "500", "-f", "raw", "-o",
                                               str(OUT / "pyspy500.txt"), "--", *DISAGG], 3),
        ("coverage", "coverage run (line coverage)", [PY, "-m", "coverage", "run", "--data-file", str(OUT / ".coverage"),
                                                     "-m", "disagg_sim", *ARGS], 3),
        ("coverage_branch", "coverage run --branch", [PY, "-m", "coverage", "run", "--branch", "--data-file",
                                                      str(OUT / ".coverage_b"), "-m", "disagg_sim", *ARGS], 3),
        ("tracemalloc", "python -X tracemalloc=1 (one frame per allocation)", [PY, "-X", "tracemalloc=1", *DISAGG[1:]], 3),
        ("tracemalloc25", "python -X tracemalloc=25 (25 frames)", [PY, "-X", "tracemalloc=25", *DISAGG[1:]], 3),
    ]
    rows = []
    for key, label, cmd, n in cases:
        xs = timed(cmd, n)
        rows.append({"key": key, "label": label, "runs": n, "median_s": st.median(xs), "samples": xs})
        print(key, [round(x, 2) for x in xs], flush=True)
    base = rows[0]["median_s"]
    for r in rows:
        r["slowdown"] = r["median_s"] / base
    R["overheads"] = rows
    # what cProfile reported (the last run's profile)
    s = io.StringIO()
    stats = pstats.Stats(str(prof), stream=s)
    stats.sort_stats("tottime")
    top = []
    for (file, line, fn), (cc, nc, tt, ct, _) in sorted(stats.stats.items(), key=lambda kv: -kv[1][2])[:8]:
        top.append({"function": fn, "file": Path(file).name if file != "~" else "(built-in)", "calls": nc,
                    "tottime": tt, "cumtime": ct})
    R["cprofile_top"] = top
    R["cprofile_total_calls"] = sum(v[1] for v in stats.stats.values())
    R["cprofile_total_s"] = stats.total_tt


def tracemalloc_peak():
    code = ("import tracemalloc, json, sys\n"
            "from disagg_sim.cli import main\n"
            "tracemalloc.start(1)\n"
            "sys.argv = ['disagg-sim', *sys.argv[1:]]\n"
            "import contextlib, io\n"
            "with contextlib.redirect_stdout(io.StringIO()):\n"
            "    main()\n"
            "cur, peak = tracemalloc.get_traced_memory()\n"
            "top = [(str(s.traceback[0]).split('site-packages/')[-1], s.size, s.count) for s in "
            "tracemalloc.take_snapshot().statistics('lineno')[:5]]\n"
            "print(json.dumps({'current': cur, 'peak': peak, 'top': top}))\n")
    p = run([PY, "-c", code, *ARGS])
    if p.returncode:
        raise SystemExit(p.stderr[-2000:])
    R["tracemalloc"] = json.loads(p.stdout.strip().splitlines()[-1])
    rss = run(["/usr/bin/time", "-v", *DISAGG]).stderr
    R["max_rss_kb"] = int(re.search(r"Maximum resident set size \(kbytes\): (\d+)", rss)[1])


def cachegrind_slowdown():
    rows = []
    for key, label, cmd in (("rust", "Rust disagg-rs, 500 requests", [str(RUST), "--n", "500", "--rate", "4", "--seed", "1"]),
                            ("python", "Python disagg-sim, 500 requests", [PY, "-m", "disagg_sim", "--requests", "500",
                                                                           "--rate", "4", "--seed", "1"])):
        native = st.median(timed(cmd, 5))
        vg = timed(["valgrind", "--tool=cachegrind", "--cache-sim=yes", f"--cachegrind-out-file={OUT}/cg.{key}.out", *cmd], 1)[0]
        rows.append({"key": key, "label": label, "native_s": native, "cachegrind_s": vg, "slowdown": vg / native})
        print(key, native, vg, flush=True)
    R["cachegrind"] = rows


# ── 2. hardware counters: multiplexing when you ask for more than the PMU has ──
EV12 = ["cycles", "instructions", "cache-references", "cache-misses", "branches", "branch-misses", "L1-dcache-loads",
        "L1-dcache-load-misses", "LLC-loads", "LLC-load-misses", "dTLB-loads", "dTLB-load-misses"]
RUST_LONG = [str(RUST), "--n", "20000", "--rate", "4", "--seed", "1"]


def perf_csv(events, repeats=5):
    p = run(["perf", "stat", "-x", ",", "-r", str(repeats), "-e", ",".join(events), "--", *RUST_LONG])
    rows = {}
    for line in p.stderr.splitlines():
        f = line.split(",")
        if len(f) >= 6 and f[2] in events:
            rows[f[2]] = {"value": float(f[0]) if f[0] not in ("<not counted>", "<not supported>") else None,
                          "variance_pct": f[3].strip("%") or None, "running_pct": float(f[5]) if f[5] else None}
    return rows, p.stderr


def multiplexing():
    para = Path("/proc/sys/kernel/perf_event_paranoid").read_text().strip()
    R["perf_paranoid"] = para
    alone, _ = perf_csv(["cycles", "instructions"])
    many, raw = perf_csv(EV12)
    (OUT / "perf_stat_12_events.txt").write_text(raw)
    R["multiplex"] = {"alone": alone, "many": many}


# ── 3. energy and GPU telemetry: try them, record what happens ────────────
def energy_probes():
    p = run(["perf", "stat", "-a", "-e", "power/energy-pkg/", "--", "sleep", "1"])
    q = run(["perf", "stat", "-e", "power/energy-pkg/", "--", "sleep", "1"])
    rapl = Path("/sys/class/powercap/intel-rapl:0/energy_uj")
    try:
        rapl.read_text()
        rapl_read = "readable"
    except PermissionError as e:
        rapl_read = f"PermissionError: {e.strerror}"
    except FileNotFoundError:
        rapl_read = "absent"
    gpu = run(["bash", "-c", "lspci | grep -i -E 'vga|3d controller'"]).stdout.strip()
    R["energy"] = {
        "perf_pkg_systemwide": {"exit": p.returncode, "stderr": p.stderr.strip()[:400]},
        "perf_pkg_task": {"exit": q.returncode, "stderr": q.stderr.strip()[:400]},
        "rapl_sysfs": {"path": str(rapl), "mode": oct(rapl.stat().st_mode & 0o777) if rapl.exists() else None,
                       "owner_uid": rapl.stat().st_uid if rapl.exists() else None, "read": rapl_read,
                       "max_energy_range_uj": int((rapl.parent / "max_energy_range_uj").read_text()),
                       "constraint_0": (rapl.parent / "constraint_0_name").read_text().strip(),
                       "constraint_0_max_power_uw": int((rapl.parent / "constraint_0_max_power_uw").read_text())},
        "perf_power_events": [ln.split()[0] for ln in run(["perf", "list", "pmu"]).stdout.splitlines()
                              if ln.strip().startswith("power/")],
        "nvidia_smi": shutil.which("nvidia-smi"), "dcgmi": shutil.which("dcgmi"), "gpu": gpu,
    }


def main():
    if len(sys.argv) > 2:                     # python run_t12.py OUTDIR energy_probes ... : re-run sections only
        R.update(json.loads((OUT / "results.json").read_text()))
        for name in sys.argv[2:]:
            globals()[name]()
        (OUT / "results.json").write_text(json.dumps(R, indent=1) + "\n")
        return
    R["cpu"] = re.search(r"Model name:\s*(.*)", run(["lscpu"]).stdout)[1].strip()
    R["loadavg_start"] = Path("/proc/loadavg").read_text().split()[:3]
    energy_probes()
    overheads()
    tracemalloc_peak()
    cachegrind_slowdown()
    multiplexing()
    R["retries"] = RETRIES
    (OUT / "results.json").write_text(json.dumps(R, indent=1) + "\n")
    print("wrote", OUT / "results.json")


if __name__ == "__main__":
    main()
