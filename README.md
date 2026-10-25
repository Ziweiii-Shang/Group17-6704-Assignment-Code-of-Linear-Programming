# Capacitated Rail Freight Routing with Time Windows

Group 17 / 6704 project: minimum-cost multicommodity rail routing with divisible freight, shared physical-arc capacities, and commodity-specific travel-time limits. The repository brings together genetic and k-neighborhood heuristics, Pruned Time-Expanded LP (PTE-LP) experiment records, and a CPLEX-based column-generation implementation.

## Repository structure

```text
src/# Baseline heuristics and GA retuning scripts# Column generation with exact RCSP pricing
data/                    # See paths below (no original Excel workbooks supplied)
  processed/              # Nine validated instance caches (.input.pkl)
  raw/                    # Place original Excel instances here for CG
results/                   # Original, retuned, and combined result tables# PTE tables, plots, JSON, solver logs, and solutions
docs/                     # Methodology, baseline analysis, and source checksums
```

## Quick start

Use Python 3.10+ in a virtual environment and run these commands from the repository root:

```bash
python -m venv .venv
source .venv/bin/activate          # Windows: .venv\Scripts\activate
python -m pip install -r requirements.txt
python src/heuristics/run_heuristics.py --instances instance_random_timewindow_small --seeds 42
python src/heuristics/run_heuristics.py   # All nine instances; seeds 42, 43, 44
python src/heuristics/run_ga_retune.py   # Retuned corridor middle / Large
```

New heuristic outputs go to `results/generated/heuristics/`; each run overwrites its generated result files. Archived results remain under `results/heuristics/`. The caches contain the data required by the heuristics; load pickle files only from trusted sources.

Column generation additionally requires the IBM CPLEX Python API and an appropriate solver license (`python -m pip install cplex`). Supply an original workbook with `Arcs`, `Commodities`, and `Costs` sheets; required columns are documented in the source:

```bash
python src/column_generation/column_generation.py --inputdata/raw/instance_corridor_timewindow_small.xlsx
```

The default CG output is `results/generated/column_generation/cg_result.xlsx` (summary, path flows, and iterations). Original Excel workbooks and CG result files were not supplied. PTE solver/counting/analysis scripts were also absent, so this repository preserves PTE results but cannot rerun that pipeline. See [PTE methodology](docs/pte_methodology.md).

## Results and interpretation

- Nine instances cover random, corridor, and hub networks at three sizes. PTE-LP solved the three random instances optimally; corridor/hub hit representation limits, which do **not** establish infeasibility.
- Baseline random-instance gaps are 0.30–0.50% for k-neighborhood and 0.36–0.71% for the six-path GA. The six-path GA leaves demand unmet on corridor middle/Large.
- GA retuning increases those two path budgets to 10 and 16 and obtains feasible costs of **730,467.34** and **906,575.20**. [Combined results](results/heuristics/results_with_retuned_ga.csv) apply these updates; [baseline results](results/heuristics/results.csv) and [retuned records](results/heuristics/results_ga_retuned.json) remain separate.
- PTE tables are in [main_results.csv](results/pte/summary/main_results.csv); figures are in [results/pte/figures/](results/pte/figures/). Compare feasibility alongside cost; missing objectives are not zero, and recorded runtimes do not establish cross-method speedups.

[Baseline analysis](docs/heuristic_analysis.md) describes the original six-path GA only. [Source manifest](docs/source_manifest.json) records original paths and SHA-256 checksums; three copied Python files received path/CLI changes. Dependencies in `requirements.txt` are unpinned; the original PTE environment pins are retained separately in `docs/pte_original_requirements.txt` as historical metadata. No license has been assigned; choose one before granting reuse rights.
