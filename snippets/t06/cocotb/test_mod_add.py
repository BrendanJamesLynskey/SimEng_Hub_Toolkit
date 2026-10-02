"""cocotb testbench: drive random and corner-case operands, check every result
against a Python golden model, and require every functional-coverage bin to be hit."""

import random

import cocotb
from cocotb.clock import Clock
from cocotb.triggers import FallingEdge, ReadOnly, RisingEdge

Q = 65521


def golden(a: int, b: int) -> int:
    """The reference model: what the hardware must compute."""
    return (a + b) % Q


def stimulus(rng: random.Random, n: int):
    """Constrained random: mostly uniform, plus the corners a uniform draw rarely hits."""
    corners = [(0, 0), (Q - 1, 0), (Q - 1, 1), (Q - 1, Q - 1), (Q // 2, Q - Q // 2)]
    yield from corners
    for _ in range(n):
        yield rng.randrange(Q), rng.randrange(Q)


@cocotb.test()
async def matches_golden_model_with_full_coverage(dut):
    cocotb.start_soon(Clock(dut.clk, 10, unit="ns").start())
    dut.rst_n.value, dut.in_valid.value = 0, 0
    await RisingEdge(dut.clk)
    dut.rst_n.value = 1

    bins = {"no wrap": 0, "wrap": 0, "sum == Q (result 0)": 0, "max operands": 0}
    for a, b in stimulus(random.Random(2026), 2000):
        await FallingEdge(dut.clk)                      # drive away from the active edge
        dut.a.value, dut.b.value, dut.in_valid.value = a, b, 1
        await RisingEdge(dut.clk)
        await ReadOnly()                                # sample after the register updates
        assert dut.out_valid.value == 1
        assert int(dut.r.value) == golden(a, b), f"{a} + {b}: got {int(dut.r.value)}"
        bins["wrap" if a + b >= Q else "no wrap"] += 1
        bins["sum == Q (result 0)"] += a + b == Q
        bins["max operands"] += a == b == Q - 1

    dut._log.info("coverage: %s", bins)
    assert all(bins.values()), f"coverage hole: {bins}"
