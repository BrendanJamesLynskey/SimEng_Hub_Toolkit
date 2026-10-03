"""Deck 12: the PyTorch profiler and ONNX Runtime's profiler on the same small model, on a CPU.

Runs in Torch_Sim_Frontend's virtualenv (CPU PyTorch, transformers, onnx, onnxruntime):

    ../../../Torch_Sim_Frontend/.venv/bin/python framework_profilers.py OUTDIR

The model is Torch_Sim_Frontend's two-layer tiny Llama with random float32 weights, one
128-token prompt, no KV cache; the ONNX graph is exported with simfront's own exporter.
Records the profilers' overheads, what each attributes the time to, and an excerpt of
ORT's Chrome-trace JSON.
"""

from __future__ import annotations

import json
import statistics as st
import sys
import time
from collections import defaultdict
from pathlib import Path

import numpy as np
import onnxruntime as ort
import torch
from simfront.capture.onnx_walk import export_onnx
from simfront.models import build, tiny_llama

OUT = Path(sys.argv[1] if len(sys.argv) > 1 else "fp_out")
OUT.mkdir(parents=True, exist_ok=True)
torch.set_num_threads(4)
R: dict = {"torch": torch.__version__, "onnxruntime": ort.__version__, "threads": 4}


def times(fn, n=30, warm=5):
    for _ in range(warm):
        fn()
    xs = []
    for _ in range(n):
        t = time.perf_counter()
        fn()
        xs.append(time.perf_counter() - t)
    return xs


def main():
    model = build(tiny_llama(), device="cpu", dtype=torch.float32, seed=0)
    x = torch.randint(0, 1000, (1, 128))
    fwd = lambda: model(x, use_cache=False)  # noqa: E731
    with torch.no_grad():
        plain = times(fwd)
        from torch.profiler import ProfilerActivity, profile
        with profile(activities=[ProfilerActivity.CPU], record_shapes=True) as prof:
            prof_t = times(fwd, n=30, warm=0)
    ka = prof.key_averages()
    rows = sorted(ka, key=lambda e: -e.self_cpu_time_total)[:8]
    tot = sum(e.self_cpu_time_total for e in ka)
    R["torch_profiler"] = {
        "plain_median_ms": 1e3 * st.median(plain), "profiled_median_ms": 1e3 * st.median(prof_t),
        "overhead": st.median(prof_t) / st.median(plain), "events": len(prof.events()),
        "top_self_cpu": [{"op": e.key, "calls": e.count, "self_cpu_ms": e.self_cpu_time_total / 1e3,
                          "share_pct": 100 * e.self_cpu_time_total / tot} for e in rows]}
    print(R["torch_profiler"], flush=True)

    path = OUT / "tiny_llama.onnx"
    names, _ = export_onnx(model, (x,), path, {"use_cache": False}, weights=True)
    feed = {names[0]: x.numpy().astype(np.int64)}

    def session(profiling: bool):
        so = ort.SessionOptions()
        so.intra_op_num_threads = 4
        so.enable_profiling = profiling
        if profiling:
            so.profile_file_prefix = str(OUT / "ort_profile")
        return ort.InferenceSession(str(path), so, providers=["CPUExecutionProvider"])

    s0 = session(False)
    ort_plain = times(lambda: s0.run(None, feed))
    s1 = session(True)
    first = time.perf_counter()
    s1.run(None, feed)
    first = time.perf_counter() - first
    ort_prof = times(lambda: s1.run(None, feed), warm=4)
    trace = Path(s1.end_profiling())
    ev = json.loads(trace.read_text())
    by_op, n_node = defaultdict(float), 0
    for e in ev:
        if e.get("cat") == "Node" and e.get("name", "").endswith("_kernel_time"):
            by_op[e["args"]["op_name"]] += e["dur"]
            n_node += 1
    tot = sum(by_op.values())
    sess_init = next((e["dur"] for e in ev if e.get("name") == "session_initialization"), None)
    excerpt = [e for e in ev if e.get("cat") == "Node" and e.get("name", "").endswith("_kernel_time")][:2]
    R["ort_profiler"] = {
        "plain_median_ms": 1e3 * st.median(ort_plain), "profiled_median_ms": 1e3 * st.median(ort_prof),
        "overhead": st.median(ort_prof) / st.median(ort_plain), "first_run_ms": 1e3 * first,
        "session_init_ms": sess_init / 1e3 if sess_init else None, "events": len(ev), "node_events": n_node,
        "trace_kb": trace.stat().st_size // 1024,
        "top_ops": [{"op": k, "share_pct": 100 * v / tot} for k, v in sorted(by_op.items(), key=lambda kv: -kv[1])[:8]],
        "excerpt": excerpt}
    trace.rename(OUT / "ort_profile.json")
    path.unlink()
    print(R["ort_profiler"]["top_ops"], R["ort_profiler"]["overhead"], flush=True)
    (OUT / "framework_profilers.json").write_text(json.dumps(R, indent=1) + "\n")


if __name__ == "__main__":
    main()
