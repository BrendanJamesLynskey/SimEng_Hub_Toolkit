import pytest

from disagg_sim.metrics import summarise
from disagg_sim.sim import SimConfig, simulate


def test_every_request_finishes(baseline_run):
    assert all(r.finish is not None for r in baseline_run.requests)


def test_stages_sum_to_end_to_end(baseline_run):
    for r in baseline_run.requests:
        assert sum(r.stages().values()) == pytest.approx(r.e2e, abs=1e-9)


@pytest.mark.parametrize("cfg", [
    SimConfig(),
    SimConfig(mode="colocated", n_colocated=2),
    SimConfig(n_prefill=2, n_decode=2),
], ids=["1P1D", "colocated", "2P2D"])
def test_kv_is_released(cfg, small_workload):
    res = simulate(cfg, small_workload)
    assert all(i.kv_used == 0 for i in res.instances)


@pytest.mark.slow
def test_long_run_is_stable():
    from disagg_sim.workload import LengthDist, poisson_workload
    wl = poisson_workload(3.0, 3000, LengthDist(2048, 0.5), LengthDist(128, 0.5), seed=2)
    m = summarise(simulate(SimConfig(fast_forward=True), wl))
    assert m["throughput"]["slo_attainment"] > 0.9


@pytest.mark.xfail(strict=True, reason="known optimism: tensor-parallel all-reduce is not modelled")
def test_eight_devices_cost_more_than_four_in_communication():
    from disagg_sim.hardware import H100_SXM, LLAMA3_70B, CostModel
    oh = 0.5e-3                                    # fixed per-step overhead, same for both
    four = CostModel(LLAMA3_70B, H100_SXM, 4).decode([4096]).time - oh
    eight = CostModel(LLAMA3_70B, H100_SXM, 8).decode([4096]).time - oh
    assert eight > 1.01 * four / 2                 # fails: the model halves it exactly


def test_summary_matches_golden(baseline_run, golden):
    m = summarise(baseline_run)
    golden({"ttft_p99": m["latency_s"]["ttft"]["p99"], "completed": m["requests"]["completed"]})
