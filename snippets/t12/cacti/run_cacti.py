#!/usr/bin/env python3
"""Sweep CACTI 7 over SRAM capacity at one node and record area, energy, leakage and timing.

The configurations are the upstream cache.cfg with only these lines changed (so every
other assumption is CACTI's default and visible in the .cfg files written to configs/):
  -size (bytes)        swept
  -technology (u)      0.022 (22 nm, the smallest node CACTI 7 has ITRS data for)
  -associativity       1
  -cache type          "ram" (a scratchpad: no tag array)
  -UCA bank count      swept separately for the largest arrays
  -Data array cell / peripheral type   itrs-hp (default) and itrs-lstp

    CACTI=~/.local/opt/cacti python run_cacti.py     # writes configs/, out/*.txt, out/results.json
"""

import json
import os
import re
import subprocess
import time
from pathlib import Path

HERE = Path(__file__).resolve().parent
CACTI = Path(os.environ.get("CACTI", Path.home() / ".local/opt/cacti"))
KIB = 1024
SIZES = [64 * KIB, 256 * KIB, 1024 * KIB, 4096 * KIB, 16384 * KIB, 65536 * KIB]
RUNS = ([("itrs-hp", s, 1) for s in SIZES] + [("itrs-lstp", s, 1) for s in SIZES]
        + [("itrs-hp", 65536 * KIB, 8), ("itrs-hp", 65536 * KIB, 32)])


def config(cell: str, size: int, banks: int) -> str:
    text = (CACTI / "cache.cfg").read_text()
    subs = {r"^-size \(bytes\) .*$": f"-size (bytes) {size}",
            r"^-technology \(u\) .*$": "-technology (u) 0.022",
            r"^-associativity .*$": "-associativity 1",
            r'^-cache type .*$': '-cache type "ram"',
            r"^-UCA bank count .*$": f"-UCA bank count {banks}",
            r'^-Data array cell type - .*$': f'-Data array cell type - "{cell}"',
            r'^-Data array peripheral type - .*$': f'-Data array peripheral type - "{cell}"'}
    for pat, rep in subs.items():
        text, n = re.subn(pat, rep, text, count=1, flags=re.M)
        assert n == 1, pat
    return text


def grab(pattern: str, text: str) -> float:
    m = re.search(pattern, text)
    if not m:
        raise ValueError(f"{pattern!r} not in CACTI output")
    return float(m[1])


def main() -> None:
    (HERE / "configs").mkdir(exist_ok=True)
    (HERE / "out").mkdir(exist_ok=True)
    version = subprocess.run(["git", "-C", str(CACTI), "log", "-1", "--format=%H"], capture_output=True,
                             text=True).stdout.strip()
    rows = []
    for cell, size, banks in RUNS:
        name = f"sram_{size // KIB}KiB_{cell}_{banks}bank"
        cfg = HERE / "configs" / f"{name}.cfg"
        cfg.write_text(config(cell, size, banks))
        t = time.perf_counter()
        p = subprocess.run([str(CACTI / "cacti"), "-infile", str(cfg)], cwd=CACTI, capture_output=True, text=True,
                           timeout=1800)
        dt = time.perf_counter() - t
        (HERE / "out" / f"{name}.txt").write_text(p.stdout + p.stderr)
        o = p.stdout
        h, w = re.search(r"Cache height x width \(mm\): ([\d.]+) x ([\d.]+)", o).groups()
        rows.append(dict(name=name, cell=cell, size_bytes=size, banks=banks, runtime_s=round(dt, 2),
                         access_ns=grab(r"Access time \(ns\): ([\d.]+)", o),
                         cycle_ns=grab(r"Cycle time \(ns\):\s+([\d.]+)", o),
                         read_nj=grab(r"Total dynamic read energy per access \(nJ\): ([\d.]+)", o),
                         write_nj=grab(r"Total dynamic write energy per access \(nJ\): ([\d.]+)", o),
                         leak_mw=grab(r"Total leakage power of a bank \(mW\): ([\d.]+)", o) * banks,
                         area_mm2=float(h) * float(w),
                         efficiency_pct=grab(r"Area efficiency \(Memory cell area/Total area\) - ([\d.]+)", o)))
        print(rows[-1])
    (HERE / "out" / "results.json").write_text(json.dumps(dict(cacti_commit=version, node_nm=22, rows=rows),
                                                          indent=1) + "\n")


if __name__ == "__main__":
    main()
