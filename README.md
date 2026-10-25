# COMP6704 Group 17: Linear Programming

This repository contains our rail freight routing methods and experiment records. Freight can be split across routes; the model minimizes cost subject to shared arc capacities and a travel-time limit for each commodity.

## Methods

- `column_generation.py`: path-based LP with CPLEX and resource-constrained shortest-path pricing.
- `scripts/pte/`: exact pruned time-expanded LP, experiment and validation scripts.
- `run_heuristics.py`, `run_ga_retune.py`: path-pool heuristics with HiGHS flow allocation.

## Setup

For CG and heuristics, install the original dependencies in `requirements.txt` and use the same Python/CPLEX versions as the original experiments:

```bash
python -m venv .venv
source .venv/bin/activate  # Windows: .venv\Scripts\activate
python -m pip install -r requirements.txt
```

Column generation also requires IBM CPLEX Optimization Studio, its Python API, and a valid license. CPLEX is not included in `requirements.txt`.

PTE dependencies are pinned separately in `requirements-pte.txt`. Use a separate environment for PTE so its dependency versions do not change the CG and heuristic environment:

```bash
python -m venv .venv-pte
source .venv-pte/bin/activate  # Windows: .venv-pte\Scripts\activate
python -m pip install -r requirements-pte.txt
```

Nine validated instance caches are included in `data/processed/` for PTE and heuristics. The original Excel workbooks are not included; CG requires a workbook with `Arcs`, `Commodities`, and `Costs` sheets. Load pickle files only from trusted sources.

## Run CG and heuristics

```bash
python run_heuristics.py
python run_ga_retune.py
```

When the original workbook and CPLEX are available:

```bash
python column_generation.py --input path/to/instance.xlsx
```

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
