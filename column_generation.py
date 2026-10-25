
"""
Column Generation for capacitated multicommodity rail routing
with commodity-specific delivery time windows.

Time-window interpretation
--------------------------
Commodity k is released at e_k and must reach its destination no later
than l_k. It is assumed to depart when released, so any path p used by k
must satisfy:

    sum_{a in p} travel_time_a <= l_k - e_k

This turns the pricing problem into a Resource-Constrained Shortest Path
Problem (RCSP).

Input Excel sheets
------------------
Arcs:
    from_node, to_node, capacity, travel_time
Commodities:
    commodity, origin, destination, demand,
    release_time, latest_arrival, max_travel_time
Costs:
    commodity, from_node, to_node, cost

Master problem:
    IBM ILOG CPLEX

Pricing:
    Exact label-setting / label-dominance RCSP

Initialization:
    One time-feasible minimum-original-cost RCSP path per commodity.
    Big-M artificial demand variables are used only as an implementation
    device to guarantee initial RMP feasibility under shared capacities.

Install
-------
pip install pandas openpyxl networkx

IBM CPLEX Python API must also be installed.
"""

from __future__ import annotations

import argparse
import heapq
import time
from dataclasses import dataclass
from typing import Dict, List, Tuple, Optional

import cplex
from cplex import SparsePair
import pandas as pd


Arc = Tuple[str, str]
PathType = Tuple[str, ...]


# =====================================================================
# Input
# =====================================================================

def read_instance_excel(instance_file: str):
    arcs_df = pd.read_excel(instance_file, sheet_name="Arcs")
    commodities_df = pd.read_excel(
        instance_file,
        sheet_name="Commodities",
    )
    costs_df = pd.read_excel(instance_file, sheet_name="Costs")

    required_arc_columns = {
        "from_node",
        "to_node",
        "capacity",
        "travel_time",
    }
    required_commodity_columns = {
        "commodity",
        "origin",
        "destination",
        "demand",
        "release_time",
        "latest_arrival",
        "max_travel_time",
    }

    if not required_arc_columns.issubset(arcs_df.columns):
        missing = required_arc_columns - set(arcs_df.columns)
        raise ValueError(f"Arcs sheet missing columns: {missing}")

    if not required_commodity_columns.issubset(
        commodities_df.columns
    ):
        missing = (
            required_commodity_columns
            - set(commodities_df.columns)
        )
        raise ValueError(
            f"Commodities sheet missing columns: {missing}"
        )

    arcs: List[Arc] = list(
        zip(
            arcs_df["from_node"].astype(str),
            arcs_df["to_node"].astype(str),
        )
    )

    capacities = {
        (str(row.from_node), str(row.to_node)):
        float(row.capacity)
        for row in arcs_df.itertuples(index=False)
    }

    travel_times = {
        (str(row.from_node), str(row.to_node)):
        float(row.travel_time)
        for row in arcs_df.itertuples(index=False)
    }

    commodities = []

    for row in commodities_df.itertuples(index=False):
        release = float(row.release_time)
        latest = float(row.latest_arrival)
        max_travel = float(row.max_travel_time)

        if max_travel <= 0:
            raise ValueError(
                f"Commodity {row.commodity} has "
                f"non-positive max_travel_time."
            )

        if abs((latest - release) - max_travel) > 1e-6:
            raise ValueError(
                f"Commodity {row.commodity}: "
                "latest_arrival - release_time must equal "
                "max_travel_time."
            )

        commodities.append(
            {
                "name": str(row.commodity),
                "origin": str(row.origin),
                "destination": str(row.destination),
                "demand": float(row.demand),
                "release_time": release,
                "latest_arrival": latest,
                "max_travel_time": max_travel,
            }
        )

    costs = {
        (
            str(row.commodity),
            str(row.from_node),
            str(row.to_node),
        ): float(row.cost)
        for row in costs_df.itertuples(index=False)
    }

    return (
        arcs,
        capacities,
        travel_times,
        commodities,
        costs,
    )


def build_adjacency(arcs: List[Arc]):
    adjacency = {}

    for u, v in arcs:
        adjacency.setdefault(u, []).append(v)
        adjacency.setdefault(v, [])

    return adjacency


def path_edges(path: PathType) -> List[Arc]:
    return list(zip(path[:-1], path[1:]))


def path_original_cost(
    commodity_name: str,
    path: PathType,
    costs: Dict[Tuple[str, str, str], float],
) -> float:
    return sum(
        costs[(commodity_name, u, v)]
        for u, v in path_edges(path)
    )


def path_travel_time(
    path: PathType,
    travel_times: Dict[Arc, float],
) -> float:
    return sum(
        travel_times[(u, v)]
        for u, v in path_edges(path)
    )


# =====================================================================
# Exact RCSP labeling
# =====================================================================

@dataclass
class Label:
    node: str
    time: float
    cost: float
    predecessor: Optional[int]
    active: bool = True


def dominates(
    time_1: float,
    cost_1: float,
    time_2: float,
    cost_2: float,
    tolerance: float = 1e-10,
) -> bool:
    """
    Label 1 dominates Label 2 if it is no worse in both resources:
        time_1 <= time_2
        cost_1 <= cost_2
    and strictly better in at least one dimension.
    """
    no_worse = (
        time_1 <= time_2 + tolerance
        and cost_1 <= cost_2 + tolerance
    )

    strictly_better = (
        time_1 < time_2 - tolerance
        or cost_1 < cost_2 - tolerance
    )

    return no_worse and strictly_better


def rcsp_label_setting(
    adjacency,
    origin: str,
    destination: str,
    max_travel_time: float,
    arc_cost: Dict[Arc, float],
    travel_times: Dict[Arc, float],
):
    """
    Exact one-resource constrained shortest path.

    Objective:
        min sum arc_cost[a]

    Subject to:
        sum travel_time[a] <= max_travel_time

    Each label stores:
        (current node, cumulative time, cumulative cost)

    At a node, dominated labels are removed.

    Returns
    -------
    path, best_cost, best_time, labels_created

    If no feasible path exists:
        None, inf, inf, labels_created
    """
    labels: List[Label] = []
    labels_at_node: Dict[str, List[int]] = {
        node: [] for node in adjacency
    }

    start = Label(
        node=origin,
        time=0.0,
        cost=0.0,
        predecessor=None,
        active=True,
    )
    labels.append(start)
    labels_at_node[origin].append(0)

    heap = [(0.0, 0.0, 0)]

    while heap:
        current_cost, current_time, label_id = heapq.heappop(
            heap
        )

        label = labels[label_id]

        if not label.active:
            continue

        # With nonnegative adjusted costs, the first active destination
        # label popped from the cost-priority queue is the minimum-cost
        # feasible destination label.
        if label.node == destination:
            path_nodes = []
            cursor = label_id

            while cursor is not None:
                current = labels[cursor]
                path_nodes.append(current.node)
                cursor = current.predecessor

            path_nodes.reverse()

            return (
                tuple(path_nodes),
                label.cost,
                label.time,
                len(labels),
            )

        for next_node in adjacency[label.node]:
            arc = (label.node, next_node)

            new_time = (
                label.time + travel_times[arc]
            )

            if new_time > max_travel_time + 1e-10:
                continue

            new_cost = (
                label.cost + arc_cost[arc]
            )

            # ---------------------------------------------------------
            # Dominance test:
            # if an existing active label at next_node is no worse in
            # both time and cost, this new label can never lead to a
            # better feasible destination path.
            # ---------------------------------------------------------
            new_is_dominated = False

            for existing_id in labels_at_node[next_node]:
                existing = labels[existing_id]

                if not existing.active:
                    continue

                if (
                    existing.time <= new_time + 1e-10
                    and existing.cost <= new_cost + 1e-10
                ):
                    new_is_dominated = True
                    break

            if new_is_dominated:
                continue

            # Remove labels dominated by the new one.
            for existing_id in labels_at_node[next_node]:
                existing = labels[existing_id]

                if not existing.active:
                    continue

                if dominates(
                    new_time,
                    new_cost,
                    existing.time,
                    existing.cost,
                ):
                    existing.active = False

            new_label_id = len(labels)

            labels.append(
                Label(
                    node=next_node,
                    time=new_time,
                    cost=new_cost,
                    predecessor=label_id,
                    active=True,
                )
            )

            labels_at_node[next_node].append(
                new_label_id
            )

            heapq.heappush(
                heap,
                (
                    new_cost,
                    new_time,
                    new_label_id,
                ),
            )

    return (
        None,
        float("inf"),
        float("inf"),
        len(labels),
    )


# =====================================================================
# Initial time-feasible paths
# =====================================================================

def generate_initial_time_feasible_paths(
    adjacency,
    commodities,
    costs,
    travel_times,
):
    """
    Initial path for each commodity:
        minimum ORIGINAL-cost path satisfying its time limit.

    Shared capacity feasibility is NOT required here. Artificial variables
    in the RMP handle initialization if the restricted path set cannot yet
    satisfy all demands under shared capacities.
    """
    initial_paths = {}
    total_labels = 0

    for k, commodity in enumerate(commodities):
        name = commodity["name"]

        original_arc_cost = {
            arc: costs[(name, arc[0], arc[1])]
            for arc in travel_times
        }

        (
            path,
            _,
            _,
            labels_created,
        ) = rcsp_label_setting(
            adjacency=adjacency,
            origin=commodity["origin"],
            destination=commodity["destination"],
            max_travel_time=commodity[
                "max_travel_time"
            ],
            arc_cost=original_arc_cost,
            travel_times=travel_times,
        )

        total_labels += labels_created

        if path is None:
            raise RuntimeError(
                f"No time-feasible path exists for commodity "
                f"{name}. Check the generated instance."
            )

        initial_paths[k] = path

    return initial_paths, total_labels


# =====================================================================
# Restricted Master Problem
# =====================================================================

def compute_big_m(
    arcs,
    costs,
    multiplier: float = 10.0,
) -> float:
    nodes = set()

    for u, v in arcs:
        nodes.add(u)
        nodes.add(v)

    max_arc_cost = max(costs.values())

    simple_path_cost_bound = (
        max(1, len(nodes) - 1)
        * max_arc_cost
    )

    return (
        multiplier * simple_path_cost_bound + 1.0
    )


class RestrictedMasterProblem:
    """
    Mathematical RMP used for path flows:

        min sum C_p^k f_p^k

        s.t.
            sum_p f_p^k = q_k
            sum_{k,p} delta_ap f_p^k <= u_a
            f_p^k >= 0

    Only TIME-FEASIBLE paths are allowed as columns.

    Implementation detail:
        artificial variables s_k are temporarily added to the demand rows
        using a Big-M penalty so that the initial restricted model remains
        solvable even when the first real path set cannot jointly satisfy
        the shared capacities.
    """

    def __init__(
        self,
        arcs,
        capacities,
        commodities,
        costs,
        travel_times,
        big_m,
        cplex_log=False,
    ):
        self.arcs = arcs
        self.capacities = capacities
        self.commodities = commodities
        self.costs = costs
        self.travel_times = travel_times
        self.big_m = float(big_m)

        self.model = cplex.Cplex()
        self.model.objective.set_sense(
            self.model.objective.sense.minimize
        )

        if not cplex_log:
            self.model.set_log_stream(None)
            self.model.set_warning_stream(None)
            self.model.set_results_stream(None)

        self.model.parameters.lpmethod.set(
            self.model.parameters.lpmethod.values.dual
        )

        self.demand_row = {}
        self.capacity_row = {}
        self.artificial_var = {}
        self.path_var = {}

        self.path_pool = {
            k: []
            for k in range(len(commodities))
        }

        self._build_constraints()
        self._add_artificial_variables()

    def _build_constraints(self):
        # Demand equalities.
        self.model.linear_constraints.add(
            lin_expr=[
                SparsePair(ind=[], val=[])
                for _ in self.commodities
            ],
            senses=["E"] * len(self.commodities),
            rhs=[
                commodity["demand"]
                for commodity in self.commodities
            ],
            names=[
                f"demand_{commodity['name']}"
                for commodity in self.commodities
            ],
        )

        for k in range(len(self.commodities)):
            self.demand_row[k] = k

        # Shared arc capacities.
        offset = len(self.commodities)

        self.model.linear_constraints.add(
            lin_expr=[
                SparsePair(ind=[], val=[])
                for _ in self.arcs
            ],
            senses=["L"] * len(self.arcs),
            rhs=[
                self.capacities[arc]
                for arc in self.arcs
            ],
            names=[
                f"capacity_{u}_{v}"
                for u, v in self.arcs
            ],
        )

        for i, arc in enumerate(self.arcs):
            self.capacity_row[arc] = offset + i

    def _add_artificial_variables(self):
        for k, commodity in enumerate(
            self.commodities
        ):
            column = SparsePair(
                ind=[self.demand_row[k]],
                val=[1.0],
            )

            variable_index = (
                self.model.variables.get_num()
            )

            self.model.variables.add(
                obj=[self.big_m],
                lb=[0.0],
                ub=[cplex.infinity],
                names=[
                    f"artificial_{commodity['name']}"
                ],
                columns=[column],
            )

            self.artificial_var[k] = (
                variable_index
            )

    def add_path(
        self,
        commodity_index: int,
        path: PathType,
    ) -> bool:
        path = tuple(path)
        key = (commodity_index, path)

        if key in self.path_var:
            return False

        commodity = self.commodities[
            commodity_index
        ]
        commodity_name = commodity["name"]

        # Safety check: every RMP column must satisfy the commodity's
        # time-window resource bound.
        route_time = path_travel_time(
            path,
            self.travel_times,
        )

        if (
            route_time
            > commodity["max_travel_time"] + 1e-8
        ):
            raise ValueError(
                f"Attempted to add time-infeasible path "
                f"for {commodity_name}: "
                f"{route_time:.4f} > "
                f"{commodity['max_travel_time']:.4f}"
            )

        row_indices = [
            self.demand_row[commodity_index]
        ]
        row_values = [1.0]

        for arc in path_edges(path):
            row_indices.append(
                self.capacity_row[arc]
            )
            row_values.append(1.0)

        original_cost = path_original_cost(
            commodity_name,
            path,
            self.costs,
        )

        column = SparsePair(
            ind=row_indices,
            val=row_values,
        )

        variable_index = (
            self.model.variables.get_num()
        )

        self.model.variables.add(
            obj=[original_cost],
            lb=[0.0],
            ub=[cplex.infinity],
            names=[
                f"path_{commodity_name}_"
                f"{len(self.path_pool[commodity_index])}"
            ],
            columns=[column],
        )

        self.path_var[key] = variable_index
        self.path_pool[commodity_index].append(
            path
        )

        return True

    def solve(self):
        self.model.solve()

        status_code = (
            self.model.solution.get_status()
        )
        status_string = (
            self.model.solution.get_status_string()
        )

        acceptable = {
            self.model.solution.status.optimal,
            self.model.solution.status.optimal_tolerance,
        }

        if status_code not in acceptable:
            raise RuntimeError(
                f"RMP not optimal. Status: "
                f"{status_string}"
            )

        objective_with_artificial = float(
            self.model.solution.get_objective_value()
        )

        duals = (
            self.model.solution.get_dual_values()
        )

        sigma = {
            k: float(
                duals[self.demand_row[k]]
            )
            for k in self.demand_row
        }

        mu = {
            arc: float(duals[row])
            for arc, row
            in self.capacity_row.items()
        }

        values = (
            self.model.solution.get_values()
        )

        artificial_flow = {
            k: float(values[var])
            for k, var
            in self.artificial_var.items()
        }

        path_flow = {
            key: float(values[var])
            for key, var
            in self.path_var.items()
        }

        transport_objective = 0.0

        for (k, path), flow in path_flow.items():
            if flow <= 0:
                continue

            transport_objective += (
                flow
                * path_original_cost(
                    self.commodities[k]["name"],
                    path,
                    self.costs,
                )
            )

        return {
            "objective_with_artificial":
                objective_with_artificial,
            "transport_objective":
                transport_objective,
            "sigma": sigma,
            "mu": mu,
            "artificial_flow": artificial_flow,
            "path_flow": path_flow,
        }


# =====================================================================
# Pricing
# =====================================================================

def price_one_commodity(
    adjacency,
    commodity,
    costs,
    travel_times,
    sigma_k,
    mu,
):
    """
    Exact pricing problem:

        min sum_a (c_a^k - mu_a) delta_ap

        s.t.
            sum_a travel_time_a delta_ap
            <= max_travel_time_k

    Reduced cost:
        adjusted_path_cost - sigma_k
    """
    name = commodity["name"]

    adjusted_arc_cost = {
        arc:
        costs[(name, arc[0], arc[1])]
        - mu[arc]
        for arc in travel_times
    }

    (
        path,
        adjusted_path_cost,
        route_time,
        labels_created,
    ) = rcsp_label_setting(
        adjacency=adjacency,
        origin=commodity["origin"],
        destination=commodity["destination"],
        max_travel_time=commodity[
            "max_travel_time"
        ],
        arc_cost=adjusted_arc_cost,
        travel_times=travel_times,
    )

    if path is None:
        return {
            "path": None,
            "adjusted_path_cost": float("inf"),
            "route_time": float("inf"),
            "reduced_cost": float("inf"),
            "labels_created": labels_created,
        }

    reduced_cost = (
        adjusted_path_cost - sigma_k
    )

    return {
        "path": path,
        "adjusted_path_cost":
            adjusted_path_cost,
        "route_time": route_time,
        "reduced_cost": reduced_cost,
        "labels_created": labels_created,
    }


# =====================================================================
# Column Generation controller
# =====================================================================

def solve_column_generation(
    instance_file: str,
    result_file: str,
    rc_tolerance: float = 1e-8,
    artificial_tolerance: float = 1e-8,
    max_iterations: int = 500,
    big_m_multiplier: float = 10.0,
    cplex_log: bool = False,
):
    # ================================================================
    # TIMER STARTS BEFORE FILE READING
    # ================================================================
    total_start = time.perf_counter()

    (
        arcs,
        capacities,
        travel_times,
        commodities,
        costs,
    ) = read_instance_excel(instance_file)

    adjacency = build_adjacency(arcs)

    big_m = compute_big_m(
        arcs=arcs,
        costs=costs,
        multiplier=big_m_multiplier,
    )

    rmp = RestrictedMasterProblem(
        arcs=arcs,
        capacities=capacities,
        commodities=commodities,
        costs=costs,
        travel_times=travel_times,
        big_m=big_m,
        cplex_log=cplex_log,
    )

    # Initial real columns: exact time-feasible minimum-original-cost paths.
    initialization_start = time.perf_counter()

    (
        initial_paths,
        initial_labels,
    ) = generate_initial_time_feasible_paths(
        adjacency=adjacency,
        commodities=commodities,
        costs=costs,
        travel_times=travel_times,
    )

    for k, path in initial_paths.items():
        rmp.add_path(k, path)

    initialization_time = (
        time.perf_counter()
        - initialization_start
    )

    history = []
    final_solution = None

    for iteration in range(max_iterations):
        rmp_start = time.perf_counter()

        master = rmp.solve()

        rmp_time = (
            time.perf_counter() - rmp_start
        )

        artificial_total = sum(
            master["artificial_flow"].values()
        )

        pricing_start = time.perf_counter()

        pricing_results = []
        iteration_labels = 0

        for k, commodity in enumerate(
            commodities
        ):
            result = price_one_commodity(
                adjacency=adjacency,
                commodity=commodity,
                costs=costs,
                travel_times=travel_times,
                sigma_k=master["sigma"][k],
                mu=master["mu"],
            )

            iteration_labels += (
                result["labels_created"]
            )

            result["commodity_index"] = k
            result["commodity"] = (
                commodity["name"]
            )

            pricing_results.append(result)

        pricing_time = (
            time.perf_counter()
            - pricing_start
        )

        finite_rc = [
            item["reduced_cost"]
            for item in pricing_results
            if item["path"] is not None
        ]

        if not finite_rc:
            raise RuntimeError(
                "No commodity has a time-feasible "
                "pricing path."
            )

        minimum_reduced_cost = min(finite_rc)

        # --------------------------------------------------------
        # Select negative-reduced-cost columns
        # --------------------------------------------------------
        candidate_columns = [
            item
            for item in pricing_results
            if (
                    item["path"] is not None
                    and item["reduced_cost"] < -rc_tolerance
            )
        ]

        # Most negative reduced cost first
        candidate_columns.sort(
            key=lambda item: item["reduced_cost"]
        )

        # Add at most N columns in this iteration
        selected_columns = candidate_columns[
                           :50
                           ]

        new_columns = 0

        for item in selected_columns:
            if rmp.add_path(
                    item["commodity_index"],
                    item["path"],
            ):
                new_columns += 1

        history.append(
            {
                "iteration": iteration,
                "rmp_objective_with_artificial":
                    master[
                        "objective_with_artificial"
                    ],
                "transport_objective":
                    master[
                        "transport_objective"
                    ],
                "artificial_flow":
                    artificial_total,
                "columns":
                    len(rmp.path_var),
                "new_columns":
                    new_columns,
                "min_reduced_cost":
                    minimum_reduced_cost,
                "labels_created":
                    iteration_labels,
                "rmp_time_sec":
                    rmp_time,
                "pricing_time_sec":
                    pricing_time,
                "elapsed_time_sec":
                    time.perf_counter()
                    - total_start,
            }
        )

        print(
            f"Iteration {iteration:3d} | "
            f"RMP = "
            f"{master['objective_with_artificial']:12.4f} | "
            f"Artificial = "
            f"{artificial_total:10.4f} | "
            f"Columns = {len(rmp.path_var):6d} | "
            f"New = {new_columns:5d} | "
            f"Labels = {iteration_labels:9d} | "
            f"Min RC = "
            f"{minimum_reduced_cost:12.6f} | "
            f"Pricing = {pricing_time:8.3f}s"
        )

        if (
            minimum_reduced_cost
            >= -rc_tolerance
        ):
            if (
                artificial_total
                > artificial_tolerance
            ):
                raise RuntimeError(
                    "No negative-reduced-cost "
                    "time-feasible path remains, "
                    "but artificial flow is positive. "
                    "The original instance may be "
                    "infeasible, or Big-M may be too small."
                )

            final_solution = master
            print(
                "\nColumn Generation converged."
            )
            break

        if new_columns == 0:
            raise RuntimeError(
                "Negative reduced cost exists but "
                "no new path was added. Check "
                "numerical tolerances."
            )

    else:
        raise RuntimeError(
            f"Maximum iterations "
            f"({max_iterations}) reached."
        )

    # Total runtime INCLUDING input file reading and initialization,
    # stopping when the final mathematical solution has been obtained.
    total_runtime = (
        time.perf_counter() - total_start
    )

    total_rmp_time = sum(
        row["rmp_time_sec"]
        for row in history
    )

    total_pricing_time = sum(
        row["pricing_time_sec"]
        for row in history
    )

    total_labels = (
        initial_labels
        + sum(
            row["labels_created"]
            for row in history
        )
    )

    print("\n============================================")
    print(
        f"Initialization time: "
        f"{initialization_time:.4f} s"
    )
    print(
        f"Total RMP time:       "
        f"{total_rmp_time:.4f} s"
    )
    print(
        f"Total pricing time:   "
        f"{total_pricing_time:.4f} s"
    )
    print(
        f"Total labels created: "
        f"{total_labels:,}"
    )
    print(
        f"Total CG runtime:      "
        f"{total_runtime:.4f} s"
    )
    print("============================================")

    # ------------------------------------------------------------
    # Results
    # ------------------------------------------------------------
    solution_rows = []

    for (
        (k, path),
        flow,
    ) in final_solution["path_flow"].items():
        if flow <= 1e-9:
            continue

        commodity = commodities[k]
        name = commodity["name"]

        route_time = path_travel_time(
            path,
            travel_times,
        )

        solution_rows.append(
            {
                "commodity": name,
                "origin": commodity["origin"],
                "destination":
                    commodity["destination"],
                "demand":
                    commodity["demand"],
                "release_time":
                    commodity["release_time"],
                "latest_arrival":
                    commodity["latest_arrival"],
                "max_travel_time":
                    commodity["max_travel_time"],
                "path_nodes":
                    "|".join(path),
                "route_travel_time":
                    route_time,
                "arrival_time":
                    commodity["release_time"]
                    + route_time,
                "flow": flow,
                "unit_path_cost":
                    path_original_cost(
                        name,
                        path,
                        costs,
                    ),
            }
        )

    solution_df = pd.DataFrame(
        solution_rows
    )
    history_df = pd.DataFrame(history)

    summary_df = pd.DataFrame(
        [
            [
                "instance_file",
                instance_file,
            ],
            [
                "final_transport_objective",
                final_solution[
                    "transport_objective"
                ],
            ],
            [
                "iterations",
                len(history_df),
            ],
            [
                "generated_columns",
                len(rmp.path_var),
            ],
            [
                "big_m",
                big_m,
            ],
            [
                "final_artificial_flow",
                sum(
                    final_solution[
                        "artificial_flow"
                    ].values()
                ),
            ],
            [
                "initialization_time_sec",
                initialization_time,
            ],
            [
                "total_rmp_time_sec",
                total_rmp_time,
            ],
            [
                "total_pricing_time_sec",
                total_pricing_time,
            ],
            [
                "total_labels_created",
                total_labels,
            ],
            [
                "total_runtime_sec",
                total_runtime,
            ],
        ],
        columns=[
            "metric",
            "value",
        ],
    )

    output_start = time.perf_counter()

    with pd.ExcelWriter(
        result_file,
        engine="openpyxl",
    ) as writer:
        summary_df.to_excel(
            writer,
            sheet_name="Summary",
            index=False,
        )
        solution_df.to_excel(
            writer,
            sheet_name="PathFlows",
            index=False,
        )
        history_df.to_excel(
            writer,
            sheet_name="Iterations",
            index=False,
        )

    output_time = (
        time.perf_counter() - output_start
    )

    end_to_end_runtime = (
        time.perf_counter() - total_start
    )

    print(
        f"Result write time:     "
        f"{output_time:.4f} s"
    )
    print(
        f"End-to-end runtime:    "
        f"{end_to_end_runtime:.4f} s"
    )
    print(
        f"Result saved to: "
        f"{result_file}"
    )

    return (
        final_solution[
            "transport_objective"
        ],
        solution_df,
        history_df,
    )


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input", required=True, help="Source Excel instance")
    parser.add_argument("--output", default="results/generated/column_generation/cg_result.xlsx")
    parser.add_argument("--max-iterations", type=int, default=500)
    parser.add_argument("--cplex-log", action="store_true")
    args = parser.parse_args()
    from pathlib import Path
    output = Path(args.output)
    output.parent.mkdir(parents=True, exist_ok=True)
    solve_column_generation(
        instance_file=args.input,
        result_file=str(output),
        rc_tolerance=1e-8,
        artificial_tolerance=1e-8,
        max_iterations=args.max_iterations,
        big_m_multiplier=10.0,
        cplex_log=args.cplex_log,
    )


if __name__ == "__main__":
    main()
