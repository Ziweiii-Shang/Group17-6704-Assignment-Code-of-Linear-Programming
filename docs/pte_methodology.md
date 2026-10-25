# PTE-LP experiment archive

The two supplied `pte_experiments` directories were byte-identical and have been deduplicated. This archive contains nine validated input caches, 103 JSON records (including summaries), 79 solver logs, 78 compressed solutions, two CSV summaries, and three figures. Records are preserved without numerical changes.

## Reproducibility status

The original README references scripts under `work/`, including `run_pte_experiments.py`, `count_pte_native.cpp`, `run_pte_benchmarks.py`, and `analyse_pte_experiments.py`. Those scripts and the nine source Excel workbooks were absent from the supplied materials. The old reproduction commands therefore cannot be executed from this repository. The heuristic scripts can use the included caches; CG needs original Excel input.

Input caches are in `data/processed/`; PTE aggregate JSON/CSV records are in `results/pte/summary/`; per-instance JSON, logs and NPZ solutions are in `results/pte/raw/`; plots are in `results/pte/figures/`. Paths here are relative to the repository root. `docs/pte_original_requirements.txt` preserves the supplied PTE pins, which have not been validated or installed during packaging.

## Definitions

- `full_variables`: exact count of all transportation-copy and sink variables on the integer time lattice. The nine full LPs were not allocated or solved.
- `bound_variables`: exact count surviving shortest-time interval tests, before sparse forward reachability.
- `pte_variables`: exact count surviving both tests and sparse source reachability. Counts include sink arcs.
- Main runtime: Excel input + shortest-time bounds + forward expansion + backward check + LP construction + HiGHS solve. Count-only experiments, diagnostic validation, cached-data export and result writing are excluded.
- Main resource guard: 2.5 million states or 5 million transportation copies. The guard is checked in blocks and can slightly overshoot. It is an implementation resource limit, not a proof of infeasibility. Initial solver time limit is 180 seconds, with one HiGHS thread and primal/dual tolerances of 1e-7. Random–Large receives a subsequent 600-second attempt after its sequential repeat reaches the 180-second limit. All raw attempts remain available.
- `reachable_te`: exact source-reachable time expansion with the deadline test, without shortest-time suffix pruning. It retains dead ends in the LP and is not the full dense time lattice.
- Paired benchmark: the 20 shortest-budget nontrivial commodities of each original workbook, retaining original demands, costs and capacities. Three repetitions, alternating method order. Input is loaded from cache and excluded from core runtime. These reduced demands do not represent the congestion of the complete instance.
- `densecheck`: actual full integer time lattice for one shortest-budget nontrivial commodity of each workbook. These are correctness checks, not full-instance runtime comparisons.
- Native counts: independent C++ bitmap/queue expansion, commodity by commodity. It computes exact graph sizes but builds no global LP, so its runtime is not PTE-LP total runtime.
- Peak RSS: process high-water mark in a fresh process for each final main instance. Auxiliary runs share a process, so their RSS is not used for method comparisons.

## Accuracy

All positive travel times are scaled by 1,000 without rounding. All commodities share one capacity per physical arc across every retained time copy. Continuous freight variables permit splitting. The maximum path travel time is enforced by strictly increasing time states and deadline-feasible sink states, not by an average-time inequality. Each optimal solution is checked for demand residuals, flow-balance residuals, physical capacity violation, nonnegativity and exact time transitions. The raw records also include a duality gap.

The supplied CG result table contains ambiguous row labels. Only verified objective matches are presented, with original row labels preserved. A matching rounded objective is corroborating evidence, not a replacement for solver status and residual checks. CG runtimes are not used to claim method speedup because hardware and solver settings are unavailable.

## Reading the records

Main measurements use `*.pte.final.json`, except random Large, whose extended completed measurement is `*.pte.final600.json`. Exact retained sizes use `*.counts.json`. Caches are validated data rather than original workbooks. Compressed solutions store transportation/sink variable vectors and aggregate physical-arc usage. JSON records retain timings, source hashes, parameters, and validation residuals.
