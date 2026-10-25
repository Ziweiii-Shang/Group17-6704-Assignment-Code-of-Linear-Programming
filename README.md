# COMP6704 Group 17: Linear Programming

This repository contains the reproducible code and recorded results for **Large-Scale Time-Constrained Multicommodity Rail Freight Routing**. Freight is divisible, each physical arc has one cumulative capacity over the planning horizon, and every route carrying positive flow must satisfy its commodity's deadline. The model is not an average-travel-time or time-varying-capacity model.

## Repository contents

- `column_generation.py`: path-based column generation (CG), using licensed CPLEX.
- `scripts/pte/`: full/dense TE, exact PTE, size counting, validation, and benchmark scripts.
- `run_heuristics.py`, `run_ga_retune.py`: K-neighborhood and GA methods, including the separate Corridor retuning.
- `data/raw/`: all nine original Excel workbooks; `data/processed/`: matching validated caches.
- `results/`: report-facing snapshots and source workbooks; `results/report/` is generated from them.
- `results/generated/`: fresh runs and logs, ignored by Git.
- `scripts/build_report_results.py`, `scripts/network_statistics.py`: report table, figure, and network-statistic generators.

All paths are repository-relative. Run commands from the repository root.

## 1. Install environments

For CG and heuristics:

```bash
python -m venv .venv
source .venv/bin/activate
python -m pip install -r requirements.txt
```

CG additionally requires **IBM CPLEX Optimization Studio, its Python API, and a full or academic license suitable for the instance sizes**. The team completed all nine CG instances in that licensed environment. Install the compatible CPLEX Python API separately. Exact historical CG/heuristic package versions were not retained; solver versions may change runtime and generated-column counts. The repository does not modify the CG or heuristic algorithms.

For PTE, full TE, and report aggregation:

```bash
python -m venv .venv-pte
source .venv-pte/bin/activate
python -m pip install -r requirements-pte.txt
```

Historical PTE records identify Python 3.12.14, HiGHS 1.15.1, and NumPy 2.5.4. Python 3.14.6 reproduced the recorded objectives and model sizes. HiGHS needs no separate license. The exact graph counter requires a C++17 compiler (`c++`, clang++, or g++); it compiles automatically, or set `CXX`.

The original Full TE prefix measurements were made on Windows 11, Intel i7-7700, approximately 32 GiB RAM, SciPy 1.18.1, and HiGHS 1.12.0. The included runner reconstructs the same model and settings; runtime, peak memory, and the stopping prefix depend on the machine.

`docs/pte_original_requirements.txt` is retained as historical metadata; `requirements-pte.txt` is the active pinned environment.

## 2. Verify inputs and implementation

```bash
python scripts/verify_inputs.py
python scripts/pte/check_pte_implementation.py
python scripts/pte/check_reproduction.py
python -m compileall -q column_generation.py run_heuristics.py run_ga_retune.py scripts
```

Use the PTE environment for these checks. The nine workbook hashes are in [data/raw/README.md](data/raw/README.md). The pickle caches contain NumPy arrays and must be loaded only from trusted sources. Filenames use `Large` and `middle`; the report calls the latter “Medium”.

## 3. Report-result files and regeneration

The checked-in files under `results/` are the results used by the submitted report. `results/cg_original.xlsx` is the original nine-instance CG summary workbook supplied by the team; `results/full_te_prefixes.csv` records Table 3, including its source and environment-dependent fifth-prefix stop. `results/main_results.csv`, `results/paired_summary.csv`, `results/dense_validation.json`, `results/results_with_retuned_ga.csv`, and the committed figures support the PTE and heuristic sections.

Regenerate report-facing tables and Figures 3–5 without rerunning optimization:

```bash
python scripts/build_report_results.py
python scripts/network_statistics.py
```

This creates `results/report/` from the committed snapshots. The default aggregation uses the explicit mapping in `results/cg_original.xlsx`; it does not infer Corridor/Hub/Random from the workbook's inconsistent `L1-*`, `M1-*`, `S1-*` legend. The topology table distinguishes the 92% generated cross-region target from the realized `od_type` share and from the share of endpoints in different zones. The report's description of “approximately 92%” matches the cross-region demand type (about 94% in these workbooks), not the distinct cross-zone endpoint share. The output includes:

| Report item | Generated output | Main source |
| --- | --- | --- |
| Table 2 and topology statistics | `results/report/network_statistics.csv` | input workbooks and caches |
| Table 3 Full TE prefixes | `results/full_te_prefixes.csv` | recorded measurements; rerun with `scripts/pte/run_full_te_prefixes.py` |
| Table 4 dense/PTE sizes | `results/report/pte_model_sizes.csv` and PTE snapshots | native counter and PTE records |
| Table 5 Random PTE vs CG | `results/report/pte_cg_random.csv` | PTE main results + CG workbook |
| Table 6 / Figure 3 CG | `results/report/cg_results.csv`, `figure3_cg_runtime.png` | `results/cg_original.xlsx` |
| Table 7 / Figures 4–5 heuristics | `results/report/method_comparison.csv`, `figure4_heuristic_gaps.png`, `figure5_recorded_times.png` | baseline and retuned JSON |
| Pruning accuracy and paired speed checks | `results/dense_validation.json`, `results/paired_summary.csv` | dense and 20-commodity scripts |

The report's method-flow and network drawings are conceptual figures; the network statistics used in the text are generated from the supplied workbooks.

## 4. Reproduce CG and heuristics

With the licensed CPLEX environment activated, run one instance:

```bash
python column_generation.py --input data/raw/instance_random_timewindow_small.xlsx \
  --output results/generated/column_generation/instance_random_timewindow_small.xlsx
```

Run all nine in bash/zsh:

```bash
for instance in data/raw/*.xlsx; do
  python column_generation.py --input "$instance" \
    --output "results/generated/column_generation/$(basename "$instance")" || break
done
```

Every CG workbook contains `Summary`, `PathFlows`, and `Iterations`. Defaults are 500 iterations, reduced-cost and artificial-flow tolerances `1e-8`, and big-M multiplier 10. Fresh aggregation checks zero artificial flow and final pricing optimality.

Run the two heuristic pipelines:

```bash
python run_heuristics.py
python run_ga_retune.py
```

The full baseline run writes `results/generated/heuristics/results.json`; retuning writes `results_ga_retuned.json`. Baseline GA uses width 6. The additional Corridor runs use width 10 for Medium and 16 for Large. Seeds are 42, 43, and 44; the reported GA cost is the best feasible seed, while its reported search time sums the three seeds and excludes path-pool construction. See [docs/heuristic_analysis.md](docs/heuristic_analysis.md).

## 5. Reproduce Full TE and PTE experiments

Full TE Table 3 uses Random-small's nontrivial commodities sorted by `(time budget, commodity index)`. The first five indices are **29, 179, 165, 115, 289**. Each prefix runs in a separate process:

```bash
python scripts/pte/run_full_te_prefixes.py
```

Defaults are dual simplex, one thread, presolve, `1e-7` primal/dual tolerances, a 7,200-second solve limit, an 8 GiB process cap, and a 6 GiB free-memory reserve. A memory stop has no objective or solve time. A different machine may solve the fifth prefix; that is an environment effect, not an infeasibility claim. Use `--max-demands 1` for a quick test.

For PTE using the historical Excel-input timing convention:

```bash
python scripts/pte/run_pte_experiments.py --input data/raw --pattern '*.xlsx' --suffix .final
python scripts/pte/run_pte_experiments.py --input data/raw \
  --pattern instance_random_timewindow_Large.xlsx --suffix .final600 --solve-limit 600
python scripts/pte/count_complete_native.py
python scripts/pte/run_pte_benchmarks.py --repeats 3
python scripts/pte/run_dense_validation.py
python scripts/pte/analyse_pte_experiments.py
```

The cache-input alternative uses `*.input.pkl` and is faster to load; recorded tables label the actual input mode. PTE full-demand results are three Random instances `Optimal` and six Corridor/Hub instances stopped at representation limits. These limits are not infeasibility certificates. The C++ counter computes complete graph sizes for all nine instances but does not build or solve the global LP. The Python counter is retained for small diagnostics and writes limited results separately as `.counts.partial.json`; analysis rejects partial counts.

The paired benchmark uses the 20 shortest-budget nontrivial commodities, three alternating-order repetitions, and compares source-reachable TE without suffix pruning against PTE. The dense check uses the actual full lattice for one shortest-budget nontrivial commodity per instance. They are separate correctness experiments.

## 6. Aggregate fresh runs

After completing fresh CG, heuristic, and PTE runs, supply all three directories together:

```bash
python scripts/build_report_results.py \
  --cg-dir results/generated/column_generation \
  --heuristic-dir results/generated/heuristics \
  --pte-dir results/generated/pte_experiments \
  --output results/generated/report_fresh
```

Missing or incomplete instances cause an error; historical measurements are never silently substituted. Fresh runtimes and column counts may differ across licensed CPLEX, operating-system, and solver versions.

## Interpretation and maintenance

- Gap is `100 * (heuristic cost / CG cost - 1)`. The report means are approximately 0.6929% for K-neighborhood and 1.0502% for GA. The original heuristic `gap_percent` fields use PTE where a PTE optimum exists; use `results/report/method_comparison.csv` for all-nine CG gaps.
- PTE total time is input + pruning + LP construction + solve; validation/export are separate. Heuristic search excludes pool construction. Cross-method recorded times are not a controlled same-machine speedup experiment.
- The report's 89.17% K-neighborhood reduction is reproduced from displayed two-decimal times; the unrounded value is retained in `comparison_summary.json`.
- Preserve checked-in `results/` when rerunning. New logs and solver solutions belong in ignored `results/generated/`; no repair notes or private diagnostics are required in the repository.
- Keep the baseline and GA retuning separate, and do not change method parameters to force matching timings.
