"""The profile-first loop, closed: the hot spot py-spy and cachegrind found, changed, and re-measured.

py-spy put `percentile` among the top self-time functions of Disaggregated_Inference_Sim: `_dist`
sorted the same list three times (for p50, p90 and p99). The fix, sorting once, was applied to
the simulator on 2026-10-03 (`disagg_sim.metrics._dist`). This script keeps the original
three-sort version below, checks that `summarise` returns exactly the same answers with either,
and times both, alternating.

It also measures Python's start-up cost under cachegrind (interpreter and imports), and Rust's
(a one-request run), so the instructions-per-request comparison can be made fair.

    python profile_first.py OUTDIR      # writes OUTDIR/profile_first.json
"""

from __future__ import annotations

import json
import math
import re
import statistics as st
import subprocess
import sys
import time
from pathlib import Path

from disagg_sim import metrics, poisson_workload, simulate, summarise
from disagg_sim.cli import build_parser, config_from_args
from disagg_sim.workload import LengthDist

OUT = Path(sys.argv[1] if len(sys.argv) > 1 else "out")


def _percentile_original(xs: list[float], p: float) -> float:
    """The original metrics.percentile: sorts its input on every call."""
    if not xs:
        return math.nan
    s = sorted(xs)
    k = (len(s) - 1) * p / 100
    lo, hi = math.floor(k), math.ceil(k)
    return s[lo] + (s[hi] - s[lo]) * (k - lo)


def _dist_original(xs: list[float]) -> dict:
    """The original metrics._dist: three percentiles, three sorts."""
    return {"mean": metrics.fmean(xs) if xs else math.nan, "p50": _percentile_original(xs, 50),
            "p90": _percentile_original(xs, 90), "p99": _percentile_original(xs, 99),
            "max": max(xs) if xs else math.nan}


def main() -> None:
    a = build_parser().parse_args(["--requests", "3000", "--rate", "4", "--seed", "1"])
    cfg = config_from_args(a)
    wl = poisson_workload(a.rate, a.requests, LengthDist(a.prompt, a.prompt_cv), LengthDist(a.output, a.output_cv),
                          seed=a.seed)
    t0 = time.perf_counter()
    res = simulate(cfg, wl)
    sim_s = time.perf_counter() - t0
    applied = metrics._dist                  # sort once, as applied on 2026-10-03
    before, after = [], []
    for _ in range(9):
        metrics._dist = _dist_original
        t0 = time.perf_counter()
        ref = summarise(res)
        before.append(time.perf_counter() - t0)
        metrics._dist = applied
        t0 = time.perf_counter()
        new = summarise(res)
        after.append(time.perf_counter() - t0)
    metrics._dist = applied
    same = json.dumps(ref, sort_keys=True) == json.dumps(new, sort_keys=True)
    itl = sum(len(r.itls) for r in res.requests)

    # Python's fixed start-up cost under cachegrind: the interpreter plus the simulator's imports
    cg = subprocess.run(["valgrind", "--tool=cachegrind", "--cache-sim=no", "--cachegrind-out-file=/dev/null",
                         sys.executable, "-c", "import disagg_sim.cli"], capture_output=True, text=True).stderr
    startup = int(re.search(r"I\s+refs:\s+([\d,]+)", cg)[1].replace(",", ""))
    rust = Path(__file__).resolve().parents[3] / "Rust_DES_Kernel" / "target" / "release" / "disagg-rs"
    cg = subprocess.run(["valgrind", "--tool=cachegrind", "--cache-sim=no", "--cachegrind-out-file=/dev/null",
                         str(rust), "--n", "1", "--seed", "1"], capture_output=True, text=True).stderr
    rust_startup = int(re.search(r"I\s+refs:\s+([\d,]+)", cg)[1].replace(",", ""))

    out = {"simulate_s": sim_s, "summarise_before": before, "summarise_after": after,
           "median_before_s": st.median(before), "median_after_s": st.median(after),
           "speedup": st.median(before) / st.median(after), "identical": same, "itl_values": itl,
           "python_startup_instructions": startup, "rust_one_request_instructions": rust_startup}
    OUT.mkdir(parents=True, exist_ok=True)
    (OUT / "profile_first.json").write_text(json.dumps(out, indent=1))
    print(json.dumps(out, indent=1))
    assert same, "sort-once changed the answers"


if __name__ == "__main__":
    main()
