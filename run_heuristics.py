#!/usr/bin/env python3
"""k-neighborhood search and a genetic algorithm for Group 17's freight instances.

The data, travel-time scaling, shared arc capacities and divisible demands are
the same ones used by the PTE-LP experiments. A route is feasible only when
the sum of its (already scaled) arc travel times is within the commodity
deadline. Flow may split. Arc capacity is static and shared.

Both heuristics search over a pool of time-feasible paths instead of building
the time-expanded LP:

- k-neighborhood: round k lets every commodity use its first k pool paths,
  then reallocates divisible flow. k grows until the pool is exhausted.
- Genetic algorithm: each commodity keeps only six paths. Crossover and
  mutation search which six, under the same flow allocation.

The pool starts with cheap paths and random detours. If that pool cannot
carry every demand, extra detours are added around saturated arcs until the
allocation is feasible or a small round limit is reached. This is a heuristic
path restriction, not the full time-expanded model and not an unbounded
column-generation run.
"""

from __future__ import annotations

import argparse
import csv
import heapq
import json
import pickle
import random
import time
from pathlib import Path

import highspy
import numpy as np

ROOT = Path(__file__).resolve().parents[2]
DATA = ROOT / "data" / "processed"
OUT = ROOT / "results" / "generated" / "heuristics"
EPS = 1e-6
SHORT_TOL = 1e-4
ARTIFICIAL_PENALTY = 1.0e5

PTE = {
    "instance_random_timewindow_small": ("Optimal", 123886.8906434401, 19.64773483283352),
    "instance_random_timewindow_middle": ("Optimal", 243121.4155566484, 86.67032679100521),
    "instance_random_timewindow_Large": ("Optimal", 373721.3996245446, 238.8697694990551),
    "instance_corridor_timewindow_small": ("representation_limit", None, 3.4982830001972616),
    "instance_corridor_timewindow_middle": ("representation_limit", None, 7.637568166013807),
    "instance_corridor_timewindow_Large": ("representation_limit", None, 13.712152625899762),
    "instance_hub_timewindow_small": ("representation_limit", None, 7.211016416084021),
    "instance_hub_timewindow_middle": ("representation_limit", None, 45.2611436258303),
    "instance_hub_timewindow_Large": ("representation_limit", None, 57.62506533402484),
}


class Instance:
    def __init__(self, name: str):
        with open(DATA / f"{name}.input.pkl", "rb") as handle:
            raw = pickle.load(handle)
        self.name = name
        self.family = raw["config"]["NETWORK_TYPE"]
        self.size = {100: "small", 150: "middle", 200: "Large"}[int(raw["config"]["N_NODES"])]
        self.costs = np.array(raw["costs"], dtype=float)
        self.n = len(raw["nodes"])
        self.m = len(raw["arcs"])
        self.k = len(raw["commodities"])
        self.cap = np.array([float(arc[3]) for arc in raw["arcs"]], dtype=float)
        self.tau = [int(arc[4]) for arc in raw["arcs"]]
        self.origin = [int(com[1]) for com in raw["commodities"]]
        self.dest = [int(com[2]) for com in raw["commodities"]]
        self.demand = [float(com[3]) for com in raw["commodities"]]
        self.deadline = [int(com[4]) for com in raw["commodities"]]
        self.adj = [[] for _ in range(self.n)]
        for index, arc in enumerate(raw["arcs"]):
            self.adj[int(arc[1])].append((int(arc[2]), self.tau[index], index))

    def cheapest(self, commodity: int, forbid=None):
        banned = forbid or set()
        origin = self.origin[commodity]
        destination = self.dest[commodity]
        deadline = self.deadline[commodity]
        row = self.costs[commodity]
        labels = [[] for _ in range(self.n)]
        parent = [[] for _ in range(self.n)]
        labels[origin].append((0, 0.0))
        parent[origin].append((-1, -1, -1))
        queue = [(0.0, 0, origin, 0)]
        while queue:
            cost, elapsed, node, label_index = heapq.heappop(queue)
            if label_index >= len(labels[node]):
                continue
            stored_time, stored_cost = labels[node][label_index]
            if stored_time != elapsed or abs(stored_cost - cost) > 1e-7:
                continue
            if any(
                other_index != label_index and other_time <= elapsed and other_cost <= cost + 1e-8
                for other_index, (other_time, other_cost) in enumerate(labels[node])
            ):
                continue
            if node == destination:
                path = []
                cursor_node, cursor_label = node, label_index
                while parent[cursor_node][cursor_label][0] != -1:
                    previous_node, previous_label, arc = parent[cursor_node][cursor_label]
                    path.append(arc)
                    cursor_node, cursor_label = previous_node, previous_label
                path.reverse()
                return cost, tuple(path)
            for nxt, travel, arc in self.adj[node]:
                if arc in banned:
                    continue
                arrival = elapsed + travel
                if arrival > deadline:
                    continue
                updated = cost + float(row[arc])
                if any(old_time <= arrival and old_cost <= updated + 1e-8 for old_time, old_cost in labels[nxt]):
                    continue
                new_index = len(labels[nxt])
                labels[nxt].append((arrival, updated))
                parent[nxt].append((node, label_index, arc))
                heapq.heappush(queue, (updated, arrival, nxt, new_index))
        return None


def _add_path(pool, found):
    if found is not None and found[1] not in pool:
        pool.append(found[1])
        return True
    return False


def build_pool(instance: Instance, seed: int = 42, random_paths: int = 8, max_pricing_rounds: int = 6):
    """Time-feasible path pool shared by both heuristics."""
    rng = random.Random(seed)
    pools = [[] for _ in range(instance.k)]
    for commodity in range(instance.k):
        original = instance.costs[commodity].copy()
        _add_path(pools[commodity], instance.cheapest(commodity))
        if pools[commodity]:
            for arc in pools[commodity][0]:
                _add_path(pools[commodity], instance.cheapest(commodity, forbid={arc}))
        for _ in range(random_paths):
            noise = np.array([rng.uniform(0.25, 2.2) for _ in range(instance.m)])
            instance.costs[commodity] = original * noise
            _add_path(pools[commodity], instance.cheapest(commodity))
            instance.costs[commodity] = original
        instance.costs[commodity] = original
    pricing_rounds = 0
    while pricing_rounds < max_pricing_rounds:
        allocation = allocate(instance, pools)
        if allocation["demand_short"] <= SHORT_TOL:
            break
        pricing_rounds += 1
        added = 0
        dual_demand = allocation["demand_dual"]
        dual_capacity = allocation["capacity_dual"]
        for commodity in range(instance.k):
            original = instance.costs[commodity].copy()
            instance.costs[commodity] = original - dual_capacity
            found = instance.cheapest(commodity)
            instance.costs[commodity] = original
            if found is None:
                continue
            reduced = found[0] - dual_demand[commodity]
            if reduced < -1e-6 and _add_path(pools[commodity], found):
                added += 1
        if added == 0:
            break
    for commodity, pool in enumerate(pools):
        if not pool:
            raise RuntimeError(f"{instance.name} commodity {commodity} has an empty path pool")
    return pools, pricing_rounds


def allocate(instance: Instance, pools):
    """Split divisible flow over the supplied paths. Shortfall is explicit."""
    columns = []
    for commodity, pool in enumerate(pools):
        row = instance.costs[commodity]
        for path in pool:
            columns.append((commodity, path, float(sum(row[arc] for arc in path))))
    column_count = len(columns)
    model = highspy.Highs()
    model.silent()
    try:
        model.setOptionValue("threads", 1)
    except Exception:
        pass
    infinity = highspy.kHighsInf
    model.addVars(column_count, [0.0] * column_count, [infinity] * column_count)
    model.changeColsCost(column_count, list(range(column_count)), [column[2] for column in columns])
    model.addVars(instance.k, [0.0] * instance.k, [infinity] * instance.k)
    model.changeColsCost(
        instance.k,
        list(range(column_count, column_count + instance.k)),
        [ARTIFICIAL_PENALTY] * instance.k,
    )
    for commodity in range(instance.k):
        indices = [index for index, column in enumerate(columns) if column[0] == commodity]
        indices.append(column_count + commodity)
        model.addRow(instance.demand[commodity], instance.demand[commodity], len(indices), indices, [1.0] * len(indices))
    for arc in range(instance.m):
        indices = [index for index, column in enumerate(columns) if arc in column[1]]
        model.addRow(0.0, float(instance.cap[arc]), len(indices), indices, [1.0] * len(indices))
    model.run()
    status = str(model.getModelStatus()).split(".")[-1]
    if status != "kOptimal":
        raise RuntimeError(f"{instance.name} flow allocation status {status}")
    values = list(model.getSolution().col_value)
    duals = list(model.getSolution().row_dual)
    shortfall = float(sum(values[column_count:]))
    served_cost = 0.0
    usage = np.zeros(instance.m)
    max_time_violation = 0
    for index, (commodity, path, unit) in enumerate(columns):
        amount = values[index]
        if amount <= 1e-8:
            continue
        served_cost += amount * unit
        overrun = sum(instance.tau[arc] for arc in path) - instance.deadline[commodity]
        if overrun > max_time_violation:
            max_time_violation = overrun
        for arc in path:
            usage[arc] += amount
    max_capacity_violation = float(np.max(usage - instance.cap)) if instance.m else 0.0
    feasible = shortfall <= SHORT_TOL and max_capacity_violation <= 1e-5 and max_time_violation <= 0
    return {
        "objective": served_cost if feasible else None,
        "loaded_objective": served_cost,
        "demand_short": shortfall,
        "max_capacity_violation": max(0.0, max_capacity_violation),
        "max_time_violation": max_time_violation,
        "feasible": feasible,
        "demand_dual": duals[: instance.k],
        "capacity_dual": np.array(duals[instance.k : instance.k + instance.m], dtype=float),
        "paths_used": sum(len(pool) for pool in pools),
    }


def k_neighborhood(instance: Instance, pools):
    """Grow the path neighborhood from k=1 up to the full pool."""
    clock = time.perf_counter()
    deepest = max(len(pool) for pool in pools)
    history = []
    best = None
    first_feasible_k = None
    for radius in range(1, deepest + 1):
        active = [pool[: min(radius, len(pool))] for pool in pools]
        allocation = allocate(instance, active)
        point = {
            "k": radius,
            "feasible": allocation["feasible"],
            "objective": allocation["objective"],
            "demand_short": allocation["demand_short"],
            "paths": allocation["paths_used"],
        }
        history.append(point)
        if allocation["feasible"] and first_feasible_k is None:
            first_feasible_k = radius
        candidate_key = (allocation["demand_short"], allocation["loaded_objective"] if allocation["feasible"] else 1e300)
        best_key = None if best is None else (best["demand_short"], best["loaded_objective"] if best["feasible"] else 1e300)
        if best is None or candidate_key < best_key:
            best = allocation
        # Once every pool path is active, further radii do not exist.
        if radius == deepest:
            break
    best = dict(best)
    best["seconds"] = time.perf_counter() - clock
    best["history"] = history
    best["first_feasible_k"] = first_feasible_k
    best["final_k"] = deepest
    return best


def _gene(rng, pool_length, width):
    chosen = [0]
    rest = list(range(1, pool_length))
    rng.shuffle(rest)
    for index in rest:
        if len(chosen) >= width:
            break
        chosen.append(index)
    while len(chosen) < min(width, pool_length):
        chosen.append(rng.randrange(pool_length))
    return chosen[: min(width, pool_length)]


def _unique(indices, pool_length):
    ordered = []
    for index in indices:
        index = int(index) % pool_length
        if index not in ordered:
            ordered.append(index)
    if 0 not in ordered:
        ordered.insert(0, 0)
    return ordered


def genetic(instance: Instance, pools, seed: int, population_size: int, generations: int, width: int, time_limit: float):
    rng = random.Random(seed)
    clock = time.perf_counter()

    def materialize(chromosome):
        active = []
        for commodity, pool in enumerate(pools):
            picked = _unique(chromosome[commodity], len(pool))[: min(width, len(pool))]
            active.append([pool[index] for index in picked])
        return active

    def evaluate(chromosome):
        allocation = allocate(instance, materialize(chromosome))
        penalty = allocation["demand_short"] * ARTIFICIAL_PENALTY + allocation["loaded_objective"]
        return penalty, allocation

    population = [_gene_chromosome(rng, pools, width) for _ in range(population_size)]
    # One chromosome uses the cheapest paths, so the search starts from the greedy pool.
    population[0] = [list(range(min(width, len(pool)))) for pool in pools]
    scored = [(evaluate(chromosome), chromosome) for chromosome in population]
    completed = 0
    while completed < generations and time.perf_counter() - clock < time_limit:
        completed += 1
        scored.sort(key=lambda item: item[0][0])
        elites = [chromosome for _score, chromosome in scored[:2]]
        children = [gene[:] for gene in elites]
        parents = scored[: max(4, population_size // 2)]
        while len(children) < population_size:
            left = rng.choice(parents)[1]
            right = rng.choice(parents)[1]
            child = []
            for commodity in range(instance.k):
                donor = left[commodity] if rng.random() < 0.5 else right[commodity]
                gene = list(donor)
                if rng.random() < 0.2 and len(pools[commodity]) > 1:
                    slot = rng.randrange(len(gene))
                    gene[slot] = rng.randrange(len(pools[commodity]))
                child.append(_unique(gene, len(pools[commodity]))[: min(width, len(pools[commodity]))])
            children.append(child)
        population = children
        scored = [(evaluate(chromosome), chromosome) for chromosome in population]
    scored.sort(key=lambda item: item[0][0])
    allocation = scored[0][0][1]
    allocation = dict(allocation)
    allocation["seconds"] = time.perf_counter() - clock
    allocation["seed"] = seed
    allocation["generations"] = completed
    allocation["population"] = population_size
    allocation["width"] = width
    return allocation


def _gene_chromosome(rng, pools, width):
    return [_gene(rng, len(pool), width) for pool in pools]


def gap_percent(objective, reference):
    if objective is None or reference is None:
        return None
    return (objective - reference) / reference * 100.0


def public_row(instance: Instance, method: str, stats: dict):
    status, reference, recorded = PTE[instance.name]
    return {
        "instance": instance.name,
        "family": instance.family,
        "size": instance.size,
        "nodes": instance.n,
        "arcs": instance.m,
        "commodities": instance.k,
        "method": method,
        "feasible": bool(stats["feasible"]),
        "objective": stats["objective"],
        "demand_short": stats["demand_short"],
        "max_capacity_violation": stats["max_capacity_violation"],
        "max_time_violation": stats["max_time_violation"],
        "seconds": stats["seconds"],
        "pte_status": status,
        "pte_objective": reference,
        "pte_recorded_seconds": recorded,
        "gap_percent": gap_percent(stats["objective"], reference),
    }


def write_rows(rows):
    OUT.mkdir(parents=True, exist_ok=True)
    (OUT / "results.json").write_text(json.dumps(rows, indent=2))
    fieldnames = [
        "instance",
        "family",
        "size",
        "method",
        "feasible",
        "objective",
        "demand_short",
        "max_capacity_violation",
        "max_time_violation",
        "seconds",
        "pte_status",
        "pte_objective",
        "pte_recorded_seconds",
        "gap_percent",
    ]
    with open(OUT / "results.csv", "w", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames, extrasaction="ignore")
        writer.writeheader()
        writer.writerows(rows)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--instances", nargs="*", default=sorted(PTE))
    parser.add_argument("--seeds", nargs="*", type=int, default=[42, 43, 44])
    args = parser.parse_args()
    rows = []
    for name in args.instances:
        print(f"\n=== {name} ===", flush=True)
        started = time.perf_counter()
        instance = Instance(name)
        pools, pricing_rounds = build_pool(instance)
        pool_seconds = time.perf_counter() - started
        pool_sizes = [len(pool) for pool in pools]
        print(
            f"pool in {time.perf_counter() - started:.1f}s  avg_paths={sum(pool_sizes)/len(pool_sizes):.1f} "
            f"max_paths={max(pool_sizes)} pricing_rounds={pricing_rounds}",
            flush=True,
        )
        print("k-neighborhood ...", flush=True)
        kns = k_neighborhood(instance, pools)
        row = public_row(instance, "k-neighborhood", kns)
        row["pool_seconds"] = pool_seconds
        row["detail"] = {
            "pricing_rounds": pricing_rounds,
            "average_pool_paths": sum(pool_sizes) / len(pool_sizes),
            "max_pool_paths": max(pool_sizes),
            "first_feasible_k": kns["first_feasible_k"],
            "final_k": kns["final_k"],
            "history": kns["history"],
        }
        rows.append(row)
        print(
            f"  feasible={row['feasible']} obj={row['objective']} short={row['demand_short']:.4f} "
            f"gap={row['gap_percent']} first_k={kns['first_feasible_k']} sec={row['seconds']:.1f}",
            flush=True,
        )
        width = 6
        population, generations, per_seed = {
            "small": (12, 8, 40.0),
            "middle": (8, 6, 50.0),
            "Large": (6, 4, 60.0),
        }[instance.size]
        print("genetic ...", flush=True)
        ga_clock = time.perf_counter()
        best = None
        runs = []
        for seed in args.seeds:
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
        best = dict(best)
        best["seconds"] = time.perf_counter() - ga_clock
        row = public_row(instance, "genetic", best)
        row["pool_seconds"] = pool_seconds
        row["detail"] = {"width": width, "runs": runs, "chosen_seed": best["seed"]}
        rows.append(row)
        print(
            f"  best feasible={row['feasible']} obj={row['objective']} short={row['demand_short']:.4f} "
            f"gap={row['gap_percent']} sec={row['seconds']:.1f}",
            flush=True,
        )
        write_rows(rows)
    write_rows(rows)
    print(f"\nWrote {OUT / 'results.json'}", flush=True)


if __name__ == "__main__":
    main()
