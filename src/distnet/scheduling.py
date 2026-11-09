"""Multi-period model with construction scheduling (levels 4-5).

Facilities are built by crews, may have precedence constraints and only ship once
completed. See ``docs/MODEL.md`` for the formulation and the modelling choices below.
"""

from __future__ import annotations

from collections import defaultdict
from typing import Dict, List, Optional, Tuple

import pulp

from ._common import ival, make_solver
from .models import SchedulingInstance, SchedulingSolution


def assign_crews(starts: Dict[str, int], build_time: Dict[str, int], crews: List[str]):
    """Greedy interval colouring: give every construction job to a free crew.

    Interval graphs are perfect, so if at most ``len(crews)`` jobs overlap at any time
    this always succeeds. Returns ``{facility: crew}``.
    """
    free_at = {c: 0 for c in crews}
    assignment = {}
    for f in sorted(starts, key=lambda f: (starts[f], f)):
        crew = next((c for c in crews if free_at[c] <= starts[f]), None)
        if crew is None:  # cannot happen when the overlap constraint holds
            raise RuntimeError(f"no crew available for {f}")
        assignment[f] = crew
        free_at[crew] = starts[f] + build_time[f]
    return assignment


def solve_scheduling(
    instance: SchedulingInstance,
    *,
    crew_model: str = "aggregated",
    strengthen: bool = True,
    prune: bool = True,
    time_limit: Optional[float] = None,
    gap: Optional[float] = None,
    msg: bool = False,
    solver=None,
) -> SchedulingSolution:
    """Maximise total profit over the planning horizon.

    Args:
        crew_model: ``"aggregated"`` (default) uses start variables ``z[f, t]`` and limits
            the number of simultaneous constructions to the number of crews; crews are
            assigned afterwards. This removes the crew symmetry (K! equivalent solutions)
            and is much smaller. ``"indexed"`` is the textbook formulation with
            ``z[f, c, t]`` and one-job-per-crew constraints, kept for cross-checking.
        strengthen: add valid linking inequalities ``x[f,s,t] <= min(cap, demand) * active``.
        prune: skip variables that can never be useful (shipping before completion, or
            on lanes where price <= unit cost, or into zero demand).
    """
    if crew_model not in ("aggregated", "indexed"):
        raise ValueError("crew_model must be 'aggregated' or 'indexed'")
    instance.validate()
    F, S, T, K = instance.facilities, instance.service_areas, instance.periods, instance.crews
    horizon = len(T)
    bt = instance.build_time
    f_idx = {f: i for i, f in enumerate(F)}
    s_idx = {s: i for i, s in enumerate(S)}
    crew_keys = [None] if crew_model == "aggregated" else list(K)
    k_idx = {c: i for i, c in enumerate(crew_keys)}

    # ---- variables -----------------------------------------------------------------
    # Z: construction of f starts in period t (only starts that can finish in time exist)
    starts = {f: [t for t in T if t + bt[f] <= horizon] for f in F}
    Z = {
        (f, c, t): pulp.LpVariable(f"z_{f_idx[f]}_{k_idx[c]}_{t}", cat=pulp.LpBinary)
        for f in F for c in crew_keys for t in starts[f]
    }
    Y = {f: pulp.LpVariable(f"y_{f_idx[f]}", cat=pulp.LpBinary) for f in F}

    def z(f, t):
        """Start variables of (f, t) over all crew keys (empty list if t is not a valid start)."""
        return [Z[(f, c, t)] for c in crew_keys if (f, c, t) in Z]

    def started_by(f, t):
        """Linear expression: 1 iff construction of f has started in a period <= t."""
        return pulp.lpSum(v for tau in starts[f] if tau <= t for v in z(f, tau))

    def active(f, t):
        """Linear expression: 1 iff f is completed (and can ship) in period t."""
        return started_by(f, t - bt[f])

    def margin_ok(f, s, t):
        return (
            instance.unit_selling_price[s] > instance.unit_shipping_cost[f][s]
            and instance.demand[s][t] > 0
            and instance.capacity[f] > 0
        )

    arcs = [
        (f, s, t)
        for f in F for s in S for t in T
        if (not prune) or (t >= bt[f] and margin_ok(f, s, t))
    ]
    X = {
        a: pulp.LpVariable(f"x_{f_idx[a[0]]}_{s_idx[a[1]]}_{a[2]}", 0, None, pulp.LpInteger)
        for a in arcs
    }
    by_ft, by_st = defaultdict(list), defaultdict(list)
    for a in arcs:
        by_ft[(a[0], a[2])].append(a)
        by_st[(a[1], a[2])].append(a)

    # ---- objective -----------------------------------------------------------------
    prob = pulp.LpProblem("MaxProfit", pulp.LpMaximize)
    revenue = pulp.lpSum(X[a] * instance.unit_selling_price[a[1]] for a in arcs)
    shipping = pulp.lpSum(X[a] * instance.unit_shipping_cost[a[0]][a[1]] for a in arcs)
    opening = pulp.lpSum(Y[f] * instance.opening_costs[f] for f in F)
    prob += revenue - shipping - opening, "Total_Profit"

    # ---- constraints ---------------------------------------------------------------
    prob += shipping + opening <= instance.budget, "Budget"

    for f in F:
        # built at most once, and exactly once iff opened
        prob += pulp.lpSum(v for t in starts[f] for v in z(f, t)) == Y[f], f"Start_{f_idx[f]}"

    # resource limit: jobs in progress at time `now` cannot exceed the available crews
    for now in T:
        running = {
            c: pulp.lpSum(
                Z[(f, c, t)] for f in F for t in starts[f] if t <= now < t + bt[f] and (f, c, t) in Z
            )
            for c in crew_keys
        }
        for c in crew_keys:
            limit = len(K) if c is None else 1
            prob += running[c] <= limit, f"Crews_{k_idx[c]}_{now}"

    # a facility can only ship after completion
    for f in F:
        for t in T:
            if t < bt[f] and prune:
                continue
            prob += (
                pulp.lpSum(X[a] for a in by_ft[(f, t)]) <= instance.capacity[f] * active(f, t),
                f"Capacity_{f_idx[f]}_{t}",
            )
            if strengthen:
                for a in by_ft[(f, t)]:
                    bound = min(instance.capacity[f], instance.demand[a[1]][t])
                    prob += X[a] <= bound * active(f, t), f"Link_{f_idx[f]}_{s_idx[a[1]]}_{t}"

    for s in S:
        for t in T:
            prob += pulp.lpSum(X[a] for a in by_st[(s, t)]) <= instance.demand[s][t], f"Demand_{s_idx[s]}_{t}"

    # precedence: if `second` has started by t, `first` must have been completed by t.
    # (Time-indexed form: tighter than big-M and it also implies Y[second] <= Y[first].)
    for n, (first, second) in enumerate(instance.dependencies):
        for t in T:
            prob += started_by(second, t) <= active(first, t), f"Precedence_{n}_{t}"

    prob.solve(solver or make_solver(msg, time_limit, gap))

    # ---- extract solution ----------------------------------------------------------
    start_of = {}
    crew_of = {}
    for f in F:
        for c in crew_keys:
            for t in starts[f]:
                if ival(Z[(f, c, t)]) == 1:
                    start_of[f] = t
                    if c is not None:
                        crew_of[f] = c
    if crew_model == "aggregated":
        crew_of = assign_crews(start_of, bt, K)

    opened = [f for f in F if f in start_of]
    schedule: List[Tuple[str, str, int, int]] = sorted(
        ((f, crew_of[f], start_of[f], start_of[f] + bt[f]) for f in opened),
        key=lambda r: (r[2], r[0]),
    )
    crew_usage = {c: [0] * horizon for c in K}
    for f, c, s0, e0 in schedule:
        for t in range(s0, e0):
            crew_usage[c][t] += 1

    qty = {a: ival(X[a]) for a in arcs}
    allocations = [
        (f, s, t, qty[(f, s, t)]) for f in F for s in S for t in T if qty.get((f, s, t), 0) > 0
    ]
    met = {s: sum(qty[a] for t in T for a in by_st[(s, t)]) for s in S}
    return SchedulingSolution(
        status=pulp.LpStatus[prob.status],
        budget=instance.budget,
        total_revenue=sum(qty[a] * instance.unit_selling_price[a[1]] for a in arcs),
        total_opening_cost=sum(instance.opening_costs[f] for f in opened),
        total_shipping_cost=sum(qty[a] * instance.unit_shipping_cost[a[0]][a[1]] for a in arcs),
        facilities_opened=opened,
        demand_met=met,
        demand_unmet={s: sum(instance.demand[s].values()) - met[s] for s in S},
        allocations=allocations,
        schedule=schedule,
        crew_usage=crew_usage,
    )
