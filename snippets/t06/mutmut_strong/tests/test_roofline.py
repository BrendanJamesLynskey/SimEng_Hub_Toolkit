import pytest

from roofline import step_time


def test_compute_bound_time_is_flops_over_peak_plus_overhead():
    assert step_time(2e15, 1e9, 1e15, 1e12) == (2.0 + 0.5e-3, "compute")


def test_memory_bound_time_is_bytes_over_bandwidth_plus_overhead():
    assert step_time(1e9, 3e12, 1e15, 1e12) == (3.0 + 0.5e-3, "memory")


def test_a_tie_counts_as_compute_bound():
    assert step_time(1e15, 1e12, 1e15, 1e12)[1] == "compute"


def test_overhead_is_added_once():
    assert step_time(0, 0, 1e15, 1e12, overhead=0.25) == (0.25, "compute")


def test_rates_divide_not_multiply():
    t, _ = step_time(4e15, 0, 2e15, 1e12, overhead=0.0)
    assert t == pytest.approx(2.0)
