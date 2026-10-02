"""A property that is false, to watch Hypothesis find and shrink a counterexample.

Claim: "p99 TTFT stays under one second at any request rate." It does not: past
saturation the prefill queue grows without bound. Hypothesis searches the rate
range and reports the simplest rate it can find that breaks the claim.
"""

from hypothesis import given, settings
from hypothesis import strategies as st

from disagg_sim.metrics import summarise
from disagg_sim.sim import SimConfig, simulate
from disagg_sim.workload import LengthDist, poisson_workload


@settings(max_examples=40, deadline=None, derandomize=True)
@given(rate=st.floats(0.5, 20.0))
def test_ttft_p99_under_one_second_at_any_rate(rate):
    wl = poisson_workload(rate, 200, LengthDist(2048, 0.5), LengthDist(64, 0.5), seed=0)
    m = summarise(simulate(SimConfig(fast_forward=True), wl))
    assert m["latency_s"]["ttft"]["p99"] < 1.0
