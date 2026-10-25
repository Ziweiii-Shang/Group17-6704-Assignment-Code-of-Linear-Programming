#!/usr/bin/env python3
"""Retune the genetic algorithm so corridor middle and Large ship every unit.

The original run kept six paths per commodity. On those two corridor instances
that budget leaves residual demand. Here the population, generation count,
seeds and path pool stay the same. The chromosome is allowed more paths, and
the search stops at the smallest tried width that ships the whole demand.
"""

from __future__ import annotations

import json
import time

from run_heuristics import OUT, build_pool, genetic, public_row, Instance

SCHEDULE = {
    "instance_corridor_timewindow_middle": [10, 11, 12],
    "instance_corridor_timewindow_Large": [16, 17],
}
SEEDS = [42, 43, 44]
POPULATION = {"middle": (8, 6, 180.0), "Large": (6, 4, 240.0)}


def run_instance(name: str) -> dict:
    print(f"\n=== {name} ===", flush=True)
    started = time.perf_counter()
    instance = Instance(name)
    pools, pricing_rounds = build_pool(instance)
    pool_seconds = time.perf_counter() - started
    pool_sizes = [len(pool) for pool in pools]
    print(
        f"pool in {pool_seconds:.1f}s  avg_paths={sum(pool_sizes) / len(pool_sizes):.1f} "
        f"max_paths={max(pool_sizes)} pricing_rounds={pricing_rounds}",
        flush=True,
    )
    population, generations, per_seed = POPULATION[instance.size]
    tried = []
    chosen = None
    for width in SCHEDULE[name]:
        print(f"genetic width={width} ...", flush=True)
        clock = time.perf_counter()
        best = None
        runs = []
        for seed in SEEDS:
            stats = genetic(instance, pools, seed, population, generations, width, per_seed)
            runs.append(
                {
                    "seed": seed,
                    "feasible": stats["feasible"],
                    "objective": stats["objective"],
                    "demand_short": stats["demand_short"],
                    "seconds": stats["seconds"],
                    "generations": stats["generations"],
                }
            )
            print(
                f"  seed {seed} feasible={stats['feasible']} obj={stats['objective']} "
                f"short={stats['demand_short']:.4f} sec={stats['seconds']:.1f}",
                flush=True,
            )
            if best is None or (stats["demand_short"], stats["loaded_objective"]) < (
                best["demand_short"],
                best["loaded_objective"],
            ):
                best = stats
        attempt = {
            "width": width,
            "feasible": bool(best["feasible"]),
            "objective": best["objective"],
            "demand_short": best["demand_short"],
            "seconds": time.perf_counter() - clock,
            "runs": runs,
            "chosen_seed": best["seed"],
        }
        tried.append(attempt)
        if best["feasible"]:
            row = public_row(instance, "genetic", best)
            row["seconds"] = time.perf_counter() - clock
            row["pool_seconds"] = pool_seconds
            row["detail"] = {
                "width": width,
                "previous_width": 6,
                "population": population,
                "generations": generations,
                "runs": runs,
                "chosen_seed": best["seed"],
                "widths_tried": tried,
                "pricing_rounds": pricing_rounds,
                "average_pool_paths": sum(pool_sizes) / len(pool_sizes),
                "max_pool_paths": max(pool_sizes),
            }
            chosen = row
            print(
                f"  shipped at width={width} obj={row['objective']} short={row['demand_short']:.4f} "
                f"sec={row['seconds']:.1f}",
                flush=True,
            )
            break
        print(f"  width={width} still short {best['demand_short']:.4f}", flush=True)
    if chosen is None:
        raise RuntimeError(f"{name} remained infeasible at widths {SCHEDULE[name]}")
    return chosen


def main():
    OUT.mkdir(parents=True, exist_ok=True)
    rows = []
    destination = OUT / "results_ga_retuned.json"
    for name in SCHEDULE:
        rows.append(run_instance(name))
        destination.write_text(json.dumps(rows, indent=2))
        print(f"wrote {destination}", flush=True)


if __name__ == "__main__":
    main()
