# COMP6704 Group 17: Linear Programming

This repository contains our rail freight routing methods and experiment records. Freight can be split across routes; the model minimizes cost subject to shared arc capacities and a travel-time limit for each commodity.

## Methods

- `column_generation.py`: path-based LP with CPLEX and resource-constrained shortest-path pricing.
- `scripts/pte/`: exact pruned time-expanded LP, experiment and validation scripts.
- `run_heuristics.py`, `run_ga_retune.py`: path-pool heuristics with HiGHS flow allocation.

## Setup

For CG and heuristics, install the dependencies in `requirements.txt`:

```bash
python -m venv .venv
source .venv/bin/activate  # Windows: .venv\Scripts\activate
python -m pip install -r requirements.txt
```

Column generation also requires IBM CPLEX Optimization Studio, its Python API, and a valid license. CPLEX is not included in `requirements.txt`. The exact Python and CPLEX versions used for the original CG/heuristic runs were not recorded, so results from those methods may vary with the installed versions. The algorithm implementations are preserved from the original method files.

PTE dependencies are pinned separately in `requirements-pte.txt`. Use a separate environment for PTE so its dependency versions do not change the CG and heuristic environment:

```bash
python -m venv .venv-pte
source .venv-pte/bin/activate  # Windows: .venv-pte\Scripts\activate
python -m pip install -r requirements-pte.txt
```

PTE package versions are pinned in `requirements-pte.txt`, but the Python version used for the recorded experiments was not saved. HiGHS is provided through `highspy`; no separate solver installation or license is required for PTE.

The nine original Excel workbooks are included in `data/raw/`, and the corresponding validated input caches are in `data/processed/`. The workbook names and cache names match exactly; `Large` uses a capital `L`. The raw-workbook hashes are recorded in `data/raw/README.md`. PTE and heuristics use the validated caches by default; CG reads a workbook directly. Load pickle files only from trusted sources.

## Run CG and heuristics

```bash
python run_heuristics.py
python run_ga_retune.py
```

With CPLEX installed, run CG on one of the included workbooks:

```bash
python column_generation.py --input data/raw/instance_random_timewindow_small.xlsx
```

To have PTE read the original Excel files and refresh its input caches, pass the raw-data directory:

```bash
python scripts/pte/run_pte_experiments.py --input data/raw --pattern '*.xlsx' --suffix .final
```

The repository's `dense_te` implementation constructs the full integer time lattice, and `python scripts/pte/run_dense_validation.py` compares it with PTE-LP for one shortest-budget nontrivial commodity from each workbook. This is a correctness check, not a full-demand dense TE solve for all nine instances. The full-instance PTE runs and the 20-commodity paired benchmarks are separate experiments; their coverage and resource limits are documented in [docs/pte_methodology.md](docs/pte_methodology.md).

## Run PTE

Activate `.venv-pte` before running these commands. The full-instance run uses a 180-second solver limit; the report's completed Random-Large run uses 600 seconds.

```bash
python scripts/pte/run_pte_experiments.py --suffix .final
python scripts/pte/run_pte_experiments.py \
  --pattern instance_random_timewindow_Large.input.pkl \
  --suffix .final600 --solve-limit 600

python scripts/pte/count_complete_pte.py
python scripts/pte/run_pte_benchmarks.py --repeats 3
python scripts/pte/run_dense_validation.py
python scripts/pte/check_pte_implementation.py
python scripts/pte/analyse_pte_experiments.py
```

PTE scripts write new files to `results/generated/pte_experiments/`; existing result files are preserved. Corridor and Hub full-instance runs may stop at the model representation limit before optimization. This is a resource limit, not an infeasibility result. Experiment definitions and limits are described in [docs/pte_methodology.md](docs/pte_methodology.md). Python and solver runtimes can vary by machine.

The commands above create fresh raw records and derived tables/figures under `results/generated/pte_experiments/`; they do not overwrite the checked-in snapshots under `results/`. Compare generated outputs with those snapshots when reproducing the report. To refresh the checked-in snapshots, review the generated files first and copy only the report-facing outputs into `results/`.

## Verify inputs and code

From the repository root, verify the nine workbooks against their documented hashes and the matching cache metadata, then run the PTE smoke test and a syntax check:

```bash
python scripts/verify_inputs.py
python scripts/pte/check_pte_implementation.py
python -m compileall -q column_generation.py run_heuristics.py run_ga_retune.py scripts/pte
```

The PTE smoke test requires the dependencies from `requirements-pte.txt`; input verification uses the Python standard library. Pickle caches should only be loaded from trusted sources.
