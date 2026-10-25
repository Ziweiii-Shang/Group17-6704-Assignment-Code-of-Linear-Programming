# PTE-LP experiments

The repository contains nine validated input caches in `data/processed/`. The original Excel workbooks are not distributed. All PTE scripts use repository-relative paths and write new artifacts to `results/generated/pte_experiments/`; the checked-in result tables and figures are preserved.

## Model and exact pruning

Each commodity has a time-expanded copy of the physical network. Every transportation variable represents flow on one physical arc at one departure time, while sink variables collect flow that reaches the destination within its time budget. A commodity's time-expanded flow balances enforce its full demand, and one capacity row per physical arc sums flow across all commodities and time copies.

The implementation scales decimal travel times by 1,000 only when this conversion is exact. It prunes using shortest-time suffix bounds and forward reachability from each commodity's source. The time-expanded network is acyclic because all travel times are strictly positive. Pruning preserves all feasible source-to-destination routes and therefore the LP optimum. Solver solutions are checked for flow balance, demand, capacity, nonnegativity, time transitions, and duality gap.

## Experiment definitions

- `full_variables` counts all transportation copies and sink variables in the full integer time lattice. This full LP is not allocated for the nine complete instances.
- `bound_variables` counts variables retained by shortest-time interval bounds before sparse forward expansion.
- `pte_variables` counts variables retained by both shortest-time bounds and source reachability, including sink variables.
- The full-instance guard stops expansion after 2.5 million states or 5 million transportation copies. Such a stop is a representation limit, not infeasibility. The solver limit is 180 seconds, except the separate completed Random-Large attempt, which uses 600 seconds.
- The paired comparison uses each instance's 20 nontrivial commodities with the shortest budgets, unchanged demands, costs, and capacities. It compares source-reachable time expansion without shortest-time suffix pruning against PTE-LP, with three alternating-order repetitions.
- The dense validation uses one shortest-budget nontrivial commodity per instance. It compares the actual full integer time lattice against PTE-LP and checks objective equality; it is a correctness test rather than a full-instance timing benchmark.
- The independent C++ counter computes PTE graph sizes commodity by commodity. It does not construct or solve the global LP, so its time is not the PTE-LP total runtime.

## Reproduction commands

From the repository root, activate the PTE environment created with `requirements-pte.txt`, then run:

```bash
python scripts/pte/run_pte_experiments.py --suffix .final
python scripts/pte/run_pte_experiments.py --pattern instance_random_timewindow_Large.input.pkl --suffix .final600 --solve-limit 600
python scripts/pte/count_complete_pte.py
python scripts/pte/run_pte_benchmarks.py --repeats 3
python scripts/pte/run_dense_validation.py
python scripts/pte/check_pte_implementation.py
python scripts/pte/analyse_pte_experiments.py
```

The final analysis expects completed main records, exact count records, paired benchmark records, and dense-validation records. For the independent native count, compile `scripts/pte/count_pte_native.cpp` with a C++17 compiler and then run `scripts/pte/count_complete_native.py`.

HiGHS solver time and peak memory vary by machine. Reproduced statuses and feasibility should be interpreted together with the resource limits and residual checks. Rounded objective matches alone do not establish optimality.
