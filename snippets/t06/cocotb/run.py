"""Build the RTL with Icarus Verilog and run the cocotb test (python run.py)."""

from pathlib import Path

from cocotb_tools.runner import get_runner

HERE = Path(__file__).parent

runner = get_runner("icarus")
runner.build(sources=[HERE / "mod_add.sv"], hdl_toplevel="mod_add", always=True, timescale=("1ns", "1ps"))
runner.test(hdl_toplevel="mod_add", test_module="test_mod_add", test_dir=HERE)
