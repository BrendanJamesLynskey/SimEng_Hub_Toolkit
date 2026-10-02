# Examples from the Simulation Engineering Toolkit decks

Every code example shown in the decks that is not taken from a code repository lives here,
runnable. `RESULTS.md` holds the outputs the decks quote; it is written by `check_snippets.py`
in the build directory, which runs all of them.

| Directory | Deck | What it is |
|-----------|------|------------|
| `t01/cost_trait` | 01 | A cost-model trait with static and dynamic dispatch (`cargo test`) |
| `t01/borrow_error`, `t01/borrow_fixed` | 01 | The borrow-checker error from holding a reference, and the index-based fix |
| `t02/cbrt_vs_pow` | 02 | How often `f64::cbrt` and `powf(1/3)` disagree |
| `t06/pytest_demo` | 06 | Fixtures, conftest, parametrize, markers, strict xfail, a golden fixture with `--bless` (needs `disagg-sim`) |
| `t06/shrinking` | 06 | A false property and Hypothesis's shrunk counterexample (needs `disagg-sim`) |
| `t06/stateful` | 06 | A Hypothesis stateful test of an event queue; `QUEUE_BUG=lifo` injects a bug |
| `t06/mutmut_weak`, `_medium`, `_strong` | 06 | Three test suites for one function, measured with mutmut and coverage |
| `t06/gtest` | 06 | GoogleTest (fixtures, parameterised and death tests) built with ASan and UBSan |
| `t06/cocotb` | 06 | A cocotb testbench for a modular adder on Icarus Verilog (`python run.py`) |

Python dependencies: `pytest hypothesis pytest-xdist pytest-cov mutmut cocotb cmake` and
[disagg-sim](https://github.com/BrendanJamesLynskey/Disaggregated_Inference_Sim). MIT licence for the code.
