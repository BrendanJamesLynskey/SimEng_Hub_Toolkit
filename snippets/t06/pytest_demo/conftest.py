"""Shared fixtures for the simulator's tests. pytest finds this file by name."""

import json

import pytest

from disagg_sim.sim import SimConfig, simulate
from disagg_sim.workload import LengthDist, poisson_workload


def pytest_addoption(parser):
    parser.addoption("--bless", action="store_true", help="rewrite golden files instead of comparing")


@pytest.fixture(scope="session")
def baseline_run():
    """One 300-request run, built once and shared by every test that asks for it."""
    wl = poisson_workload(4.0, 300, LengthDist(2048, 0.5), LengthDist(128, 0.5), seed=1)
    return simulate(SimConfig(), wl)


@pytest.fixture
def small_workload():
    """A fresh workload per test: simulate() mutates requests, so never share one."""
    return poisson_workload(2.0, 50, LengthDist(512, 0.3), LengthDist(32, 0.3), seed=7)


@pytest.fixture
def golden(request, pytestconfig):
    """Compare a result with tests/golden/<test name>.json, or rewrite it with --bless."""
    path = request.path.parent / "golden" / f"{request.node.name}.json"

    def check(result: dict):
        if pytestconfig.getoption("bless") or not path.exists():
            path.parent.mkdir(exist_ok=True)
            path.write_text(json.dumps(result, indent=1, sort_keys=True))
            pytest.skip(f"blessed {path.name}")
        assert result == json.loads(path.read_text())

    return check
