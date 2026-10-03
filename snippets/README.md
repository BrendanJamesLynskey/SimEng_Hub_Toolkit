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
| `t07/*.Jenkinsfile`, `t07/shared-lib` | 07 | The matrix, scripted and shared-library pipelines (run as jobs on a local Jenkins), the library's `simRegression` step, and a Jenkinsfile with a deliberate typo for the linter |
| `t08/example_project.py`, `t08/jql.py` | 08 | An EXAMPLE issue log for a fictional simulator team (fixed seed, not real Jira data), a small evaluator for the subset of JQL the deck uses, and its tests (`pytest test_jql.py`) |
| `t11/run_t11.py`, `t11/profile_first.py`, `t11/out` | 11 | The profiling, cachegrind, benchmark and USE measurements (needs py-spy, valgrind and the simulators), the sort-once experiment, and the raw profiles and flame graphs they recorded |

Python dependencies: `pytest hypothesis pytest-xdist pytest-cov mutmut cocotb cmake py-spy` and
[disagg-sim](https://github.com/BrendanJamesLynskey/Disaggregated_Inference_Sim) (and, for t11,
[memsim](https://github.com/BrendanJamesLynskey/Memory_System_Sim)). MIT licence for the code.
