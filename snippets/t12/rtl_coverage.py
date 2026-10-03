"""Deck 12: Verilator's line and toggle coverage on RTL_CoSim_NTT's butterfly, and what it costs.

Runs in RTL_CoSim_NTT's virtualenv with Verilator on the PATH:

    source ~/.local/opt/verilator-deb/env.sh
    ../../../RTL_CoSim_NTT/.venv/bin/python rtl_coverage.py OUTDIR

Builds the butterfly twice (plain, and with --coverage), runs the same cocotb test
(butterfly_random, 4,000 transactions) with uniform and with constrained-random stimulus,
with the seeded Barrett bug (INJECT_BUG) and without, and counts the covered line and
toggle points from coverage.dat. The point: uniform stimulus reaches nearly every line and
toggle and still misses the bug that the functional-coverage crosses expose (SimEng 05).
"""

from __future__ import annotations

import json
import os
import re
import sys
import time
from collections import Counter
from pathlib import Path

SANDBOX = Path(__file__).resolve().parents[3]
REPO = SANDBOX / "RTL_CoSim_NTT"
sys.path.insert(0, str(REPO / "src"))
sys.path.insert(0, str(REPO / "tb"))
from ntt_cosim.primes import PRIMES  # noqa: E402
from ntt_cosim.rtl import _runner, count  # noqa: E402

OUT = Path(sys.argv[1] if len(sys.argv) > 1 else "rtl_out").resolve()
BUILD = OUT / "sim_build"
SRC = [REPO / "rtl" / s for s in ("mod_mul_barrett.sv", "ntt_butterfly.sv")]
N = 4000


def build(tag, args, defines):
    bdir = BUILD / tag
    runner = _runner("verilator")
    t = time.perf_counter()
    runner.build(verilog_sources=SRC, hdl_toplevel="ntt_butterfly", defines=defines, build_args=["-Wno-fatal", "-O3", *args],
                 build_dir=bdir, timescale=("1ns", "1ps"), always=True)
    return runner, bdir, time.perf_counter() - t


def points(dat: Path):
    """Covered/total points per type (line, toggle, ...) from a Verilator coverage.dat."""
    tot, hit = Counter(), Counter()
    for line in dat.read_text(errors="replace").splitlines():
        m = re.match(r"C '(.*)' (\d+)$", line)
        if not m:
            continue
        fields = dict(re.findall(r"\x01([^\x02]+)\x02([^\x01]*)", "\x01" + m[1]))
        kind = fields.get("page", "?").split("/")[0].removeprefix("v_")
        tot[kind] += 1
        hit[kind] += int(m[2]) > 0
    return {k: {"covered": hit[k], "points": tot[k], "pct": 100 * hit[k] / tot[k]} for k in sorted(tot)}


def main():
    os.environ["VIRTUAL_ENV"] = sys.prefix
    R = {"transactions": N, "prime": "mid", "runs": []}
    for cov in (False, True):
        for bug in (False, True):
            tag = f"{'cov' if cov else 'plain'}{'_bug' if bug else ''}"
            runner, bdir, bt = build(tag, ["--coverage"] if cov else [], {"INJECT_BUG": 1} if bug else {})
            for stim in ("uniform", "constrained"):
                out = OUT / f"bf_{tag}_{stim}.json"
                dat = bdir / "coverage.dat"
                if dat.exists():
                    dat.unlink()
                env = {"BF_PRIME": hex(PRIMES["mid"]), "BF_STIM": stim, "BF_N": str(N), "BF_SEED": "1", "BF_OUT": str(out)}
                xml = OUT / f"results_{tag}_{stim}.xml"
                t = time.perf_counter()
                runner.test(hdl_toplevel="ntt_butterfly", test_module="test_butterfly", testcase="butterfly_random",
                            build_dir=bdir, test_dir=bdir, extra_env=env, results_xml=str(xml), timescale=("1ns", "1ps"))
                rt = time.perf_counter() - t
                tests, fails = count(xml)
                fcov = json.loads(out.read_text())["coverage"] if out.exists() else None
                row = {"build": tag, "coverage": cov, "bug": bug, "stimulus": stim, "build_s": bt, "run_s": rt,
                       "tests": tests, "failures": fails,
                       "functional_holes": fcov["holes"] if fcov else None,
                       "functional_bins": len(fcov["bins"]) if fcov else None,
                       "code": points(dat) if cov and dat.exists() else None}
                R["runs"].append(row)
                print(row, flush=True)
    (OUT / "rtl_coverage.json").write_text(json.dumps(R, indent=1) + "\n")


if __name__ == "__main__":
    main()
