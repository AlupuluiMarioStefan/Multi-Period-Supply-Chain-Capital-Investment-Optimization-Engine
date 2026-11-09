"""Single-period model: facility location + allocation, optionally with carriers.

Covers levels 1-3 of the project. See ``docs/MODEL.md`` for the formulation.
"""

from __future__ import annotations

from collections import defaultdict
from typing import Optional

import pulp

from ._common import ival, make_solver
from .models import StaticInstance, StaticSolution


def solve_static(
    instance: StaticInstance,
    *,
    strengthen: bool = True,
    prune: bool = True,
    time_limit: Optional[float] = None,
    gap: Optional[float] = None,
    msg: bool = False,
    solver=None,
) -> StaticSolution:
    """Maximise profit = revenue - shipping - opening costs.

    Args:
        instance: the problem data (validated before solving).
        strengthen: add the valid inequalities ``x[f,s,c] <= min(cap, demand, volume) * y[f]``.
            They do not change the optimum but make the LP relaxation much tighter.
        prune: drop arcs that lose money (price <= unit cost) or have no demand; they can
            never be part of an optimal solution.
        time_limit / gap / msg: passed to the default CBC solver.
        solver: supply your own PuLP solver object (e.g. ``pulp.HiGHS()``).
    """
    instance.validate()
    F, S = instance.facilities, instance.service_areas
    lanes = instance.carriers or [None]  # None == direct shipping, multiplier 1
    has_carriers = bool(instance.carriers)

    def multiplier(c, s):
        return 1.0 if c is None else instance.carrier_multiplier[c][s]

    def unit_cost(f, s, c):
        return multiplier(c, s) * instance.unit_shipping_cost[f][s]

    # ---- sets of usable (facility, area, carrier) arcs ------------------------------
    arcs = []
    for f in F:
        for c in lanes:
            for s in S:
                if c is not None and s not in instance.carrier_multiplier[c]:
                    continue
                if prune and (
                    instance.unit_selling_price[s] <= unit_cost(f, s, c)
                    or instance.demand[s] == 0
                    or instance.capacity[f] == 0
                ):
                    continue
                arcs.append((f, s, c))

    # ---- variables -----------------------------------------------------------------
    f_idx = {f: i for i, f in enumerate(F)}
    s_idx = {s: i for i, s in enumerate(S)}
    c_idx = {c: i for i, c in enumerate(lanes)}
    X = {
        a: pulp.LpVariable(f"x_{f_idx[a[0]]}_{s_idx[a[1]]}_{c_idx[a[2]]}", 0, None, pulp.LpInteger)
        for a in arcs
    }
    Y = {f: pulp.LpVariable(f"y_{f_idx[f]}", cat=pulp.LpBinary) for f in F}

    by_f, by_s, by_c = defaultdict(list), defaultdict(list), defaultdict(list)
    for a in arcs:
        by_f[a[0]].append(a)
        by_s[a[1]].append(a)
        by_c[a[2]].append(a)

    # ---- model ---------------------------------------------------------------------
    prob = pulp.LpProblem("MaxProfit", pulp.LpMaximize)
    revenue = pulp.lpSum(X[a] * instance.unit_selling_price[a[1]] for a in arcs)
    shipping = pulp.lpSum(X[a] * unit_cost(*a) for a in arcs)
    opening = pulp.lpSum(Y[f] * instance.opening_costs[f] for f in F)
    prob += revenue - shipping - opening, "Total_Profit"

    for f in F:
        prob += pulp.lpSum(X[a] for a in by_f[f]) <= instance.capacity[f] * Y[f], f"Capacity_{f_idx[f]}"
    for s in S:
        prob += pulp.lpSum(X[a] for a in by_s[s]) <= instance.demand[s], f"Demand_{s_idx[s]}"
    if has_carriers:
        for c in lanes:
            prob += pulp.lpSum(X[a] for a in by_c[c]) <= instance.max_volume[c], f"Volume_{c_idx[c]}"
    prob += shipping + opening <= instance.budget, "Budget"

    if strengthen:  # linking cuts: an arc can only carry flow if its facility is open
        for n, a in enumerate(arcs):
            f, s, c = a
            bound = min(instance.capacity[f], instance.demand[s])
            if has_carriers:
                bound = min(bound, instance.max_volume[c])
            prob += X[a] <= bound * Y[f], f"Link_{n}"

    prob.solve(solver or make_solver(msg, time_limit, gap))

    # ---- extract (rounded) solution, recompute every metric from integers -----------
    qty = {a: ival(X[a]) for a in arcs}
    opened = [f for f in F if ival(Y[f]) == 1]
    order = sorted((a for a in arcs if qty[a] > 0), key=lambda a: (f_idx[a[0]], c_idx[a[2]], s_idx[a[1]]))
    allocations = [
        (f, s, c, qty[(f, s, c)]) if has_carriers else (f, s, qty[(f, s, c)]) for f, s, c in order
    ]
    met = {s: sum(qty[a] for a in by_s[s]) for s in S}
    return StaticSolution(
        status=pulp.LpStatus[prob.status],
        budget=instance.budget,
        total_revenue=sum(qty[a] * instance.unit_selling_price[a[1]] for a in arcs),
        total_opening_cost=sum(instance.opening_costs[f] for f in opened),
        total_shipping_cost=sum(qty[a] * unit_cost(*a) for a in arcs),
        facilities_opened=opened,
        demand_met=met,
        demand_unmet={s: instance.demand[s] - met[s] for s in S},
        allocations=allocations,
        volume_used={c: sum(qty[a] for a in by_c[c]) for c in instance.carriers},
    )
