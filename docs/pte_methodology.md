# PTE-LP experiments

The repository contains nine original Excel workbooks in `data/raw/` and their validated input caches in `data/processed/`. The SHA-256 hashes in `data/raw/README.md` identify the workbooks and match the source hashes embedded in their corresponding caches. All PTE scripts use repository-relative paths and write new artifacts to `results/generated/pte_experiments/`; the checked-in result tables and figures are preserved.

## Model and exact pruning

Each commodity has a time-expanded copy of the physical network. Every transportation variable represents flow on one physical arc at one departure time, while sink variables collect flow that reaches the destination within its time budget. A commodity's time-expanded flow balances enforce its full demand, and one capacity row per physical arc sums flow across all commodities and time copies.

The implementation scales decimal travel times by 1,000 only when this conversion is exact. It prunes using shortest-time suffix bounds and forward reachability from each commodity's source. The time-expanded network is acyclic because all travel times are strictly positive. Pruning preserves all feasible source-to-destination routes and therefore the LP optimum. Solver solutions are checked for flow balance, demand, capacity, nonnegativity, time transitions, and duality gap.

## Experiment definitions

- `full_variables` counts all transportation copies and sink variables in the full integer time lattice. This full LP is not allocated for the nine complete instances.
- `bound_variables` counts variables retained by shortest-time interval bounds before sparse forward expansion.
- `pte_variables` counts variables retained by both shortest-time bounds and source reachability, including sink variables.
- The full-instance guard stops expansion after 2.5 million states or 5 million transportation copies. Such a stop is a representation limit, not infeasibility. The solver limit is 180 seconds, except the separate completed Random-Large attempt, which uses 600 seconds.
- The paired comparison uses each instance's 20 nontrivial commodities with the shortest budgets, unchanged demands, costs, and capacities. It compares source-reachable time expansion without shortest-time suffix pruning against PTE-LP, with three alternating-order repetitions.
- The code includes `dense_te`, which constructs the actual full integer time lattice. The dense validation runs this model for one shortest-budget nontrivial commodity per instance and checks objective equality against PTE-LP. It verifies the pruning implementation, but it is neither a full-demand dense TE solve nor a full-instance timing benchmark. The nine full-demand dense TE LPs were not solved.
- The independent C++ counter computes PTE graph sizes commodity by commodity. It does not construct or solve the global LP, so its time is not the PTE-LP total runtime.

## Reproduction commands

From the repository root, activate the PTE environment created with `requirements-pte.txt`, then run:

```bash
python scripts/pte/run_pte_experiments.py --suffix .final
python scripts/pte/run_pte_experiments.py --pattern instance_random_timewindow_Large.input.pkl --suffix .final600 --solve-limit 600
python scripts/pte/count_complete_native.py
python scripts/pte/run_pte_benchmarks.py --repeats 3
python scripts/pte/run_dense_validation.py
python scripts/pte/check_pte_implementation.py
python scripts/pte/analyse_pte_experiments.py
```

The native counter automatically compiles `count_pte_native.cpp` with a C++17 compiler (`c++`, or the `CXX` command). It computes complete sizes for all nine instances without the Python counter's per-commodity limit. Only complete records with matching input hashes are reused; partial, malformed or legacy records without a source hash are recomputed. `--force` requests fresh counts.

`count_complete_pte.py` remains available for small diagnostics. A limited run writes `.counts.partial.json` and returns a nonzero exit status. The final analysis requires complete counts for every commodity and rejects incomplete records before writing report tables. It also needs main-run records (including representation-limit outcomes), paired benchmarks and dense-validation records.

`analyse_pte_experiments.py` writes derived tables, figures, and `summary.json` to `results/generated/pte_experiments/`. It does not refresh the checked-in snapshots under `results/`; review and copy report-facing outputs explicitly when updating those snapshots.

HiGHS solver time and peak memory vary by machine. Reproduced statuses and feasibility should be interpreted together with the resource limits and residual checks. Rounded objective matches alone do not establish optimality.

Historical PTE records identify Python 3.12.14, HiGHS 1.15.1 and NumPy 2.5.4. The commands above read pickle caches; historical main experiments read Excel. For matching input timing, use the Excel-input alternatives in the root README. Tables include `input_mode`, and the runtime chart labels the actual input mode. `total_seconds` is input + pruning + LP construction + LP solve, excluding separately recorded validation/export overhead. Compare timings only with these definitions and input modes aligned.
