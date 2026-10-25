# Recorded results and provenance

The files in this directory are the report-facing snapshots. They are kept separate from `results/generated/`, which is ignored and contains fresh logs, solver solution files, and temporary outputs.

## Input and method mapping

- `cg_original.xlsx` is the original CG summary workbook supplied by the team. `Sheet1` contains the nine rows used for the report's CG cost, runtime, and generated-column table. The source labels are `L1-*`, `M1-*`, and `S1-*`; the legend in that workbook is inconsistent with the row values, so `scripts/build_report_results.py` uses an explicit mapping: `L` = Corridor, `M` = Hub, `S` = Random; suffix 1/2/3 = Large/Middle/Small.
- `main_results.csv`, `summary.json`, `model_size.png`, `runtime_breakdown.png`, and `paired_summary.csv` are PTE summaries and figures. They retain representation-limit outcomes for six Corridor/Hub full-demand runs; a representation limit is not infeasibility.
- `results.json`, `results_ga_retuned.json`, `results.csv`, and `results_with_retuned_ga.csv` are the baseline and separately retuned heuristic snapshots. The retuned GA rows replace only the infeasible baseline GA rows for Corridor-Middle and Corridor-Large in report comparisons. Baseline and retuned runs remain identifiable in the source JSON files.
- `dense_validation.json` checks one actual full-lattice TE model against PTE for one nontrivial commodity per instance. `paired_benchmarks.json` and `paired_summary.csv` compare 20-commodity source-reachable TE and PTE. Neither is a full-demand dense TE run.
- `full_te_prefixes.csv` is the report's Random-Small progressive Full TE table. Its first four rows are completed prefix LPs, and its fifth row records the original free-memory stop. A different machine may complete that fifth prefix.
- `report/pte_model_sizes.csv` is the compact report table of full-lattice and retained-PTE variables. It is a size calculation; it does not claim that the full-demand dense LP was solved.

## Regenerating report tables

From the repository root, run:

```bash
python scripts/build_report_results.py
python scripts/network_statistics.py
```

The generated report directory is `results/report/`. The aggregation validates all nine instance names, feasible heuristic rows, PTE Random optima, and CG convergence fields when fresh CG workbooks are supplied. It never fills missing fresh results from historical snapshots.

## Reproducing recorded optimization

Use the commands in the root README. CG requires a full or academic CPLEX license for all nine instances. PTE and heuristic inputs are the nine workbooks under `data/raw/`; `data/processed/` caches contain matching source hashes. Runtime and peak memory are machine-dependent, while objectives and feasibility should be compared with the recorded values.

## Data integrity

`data/raw/README.md` lists SHA-256 checksums for all nine input workbooks. `scripts/verify_inputs.py` verifies every workbook/cache pair before loading experiment data.
