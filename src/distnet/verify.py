"""Independent solution checker.

Re-derives every constraint of the problem directly from the instance data, without
using any solver code. Used by the CLI and the test-suite.
"""

from __future__ import annotations

from collections import defaultdict
from typing import List

from .models import (
    SchedulingInstance,
    SchedulingSolution,
    Solution,
    StaticInstance,
    StaticSolution,
)

TOL = 1e-6


def verify_static(inst: StaticInstance, sol: StaticSolution) -> List[str]:
    errors: List[str] = []
    opened = set(sol.facilities_opened)
    by_f, by_s, by_c = defaultdict(int), defaultdict(int), defaultdict(int)
    revenue = shipping = 0.0
    for row in sol.allocations:
        if len(row) == 4:
            f, s, c, q = row
        else:
            (f, s, q), c = row, None
        if q < 0:
            errors.append(f"negative quantity on {row}")
        if f not in opened and q > 0:
            errors.append(f"{f} ships but is not opened")
        mult = 1.0
        if c is not None:
            if s not in inst.carrier_multiplier.get(c, {}):
                errors.append(f"carrier {c} does not serve {s}")
                continue
            mult = inst.carrier_multiplier[c][s]
        by_f[f] += q
        by_s[s] += q
        by_c[c] += q
        revenue += q * inst.unit_selling_price[s]
        shipping += q * mult * inst.unit_shipping_cost[f][s]
    for f in inst.facilities:
        if by_f[f] > inst.capacity[f] + TOL:
            errors.append(f"capacity of {f} exceeded: {by_f[f]} > {inst.capacity[f]}")
    for s in inst.service_areas:
        if by_s[s] > inst.demand[s] + TOL:
            errors.append(f"demand of {s} exceeded: {by_s[s]} > {inst.demand[s]}")
    for c in inst.carriers:
        if by_c[c] > inst.max_volume[c] + TOL:
            errors.append(f"volume of carrier {c} exceeded: {by_c[c]} > {inst.max_volume[c]}")
    opening = sum(inst.opening_costs[f] for f in opened)
    if shipping + opening > inst.budget + TOL:
        errors.append(f"budget exceeded: {shipping + opening} > {inst.budget}")
    _check_totals(errors, sol, revenue, opening, shipping)
    return errors


def verify_scheduling(inst: SchedulingInstance, sol: SchedulingSolution) -> List[str]:
    errors: List[str] = []
    horizon = len(inst.periods)
    start, end, crew = {}, {}, {}
    for f, c, s0, e0 in sol.schedule:
        if f in start:
            errors.append(f"{f} is built more than once")
        start[f], end[f], crew[f] = s0, e0, c
        if e0 - s0 != inst.build_time[f]:
            errors.append(f"{f}: duration {e0 - s0} != build_time {inst.build_time[f]}")
        if s0 < 0 or e0 > horizon:
            errors.append(f"{f}: construction [{s0},{e0}) leaves the horizon")
        if c not in inst.crews:
            errors.append(f"{f}: unknown crew {c}")
    if set(start) != set(sol.facilities_opened):
        errors.append("facilities_opened does not match the construction schedule")
    # a crew builds at most one facility at a time
    for c in inst.crews:
        jobs = sorted((start[f], end[f], f) for f in start if crew[f] == c)
        for (s1, e1, f1), (s2, e2, f2) in zip(jobs, jobs[1:]):
            if s2 < e1:
                errors.append(f"crew {c}: {f1} [{s1},{e1}) overlaps {f2} [{s2},{e2})")
    # precedence
    for first, second in inst.dependencies:
        if second in start and (first not in start or end[first] > start[second]):
            errors.append(f"dependency ({first}, {second}) violated")
    # shipping
    by_ft, by_st = defaultdict(int), defaultdict(int)
    revenue = shipping = 0.0
    for f, s, t, q in sol.allocations:
        if f not in end or t < end[f]:
            errors.append(f"{f} ships in period {t} before it is completed")
        by_ft[(f, t)] += q
        by_st[(s, t)] += q
        revenue += q * inst.unit_selling_price[s]
        shipping += q * inst.unit_shipping_cost[f][s]
    for (f, t), q in by_ft.items():
        if q > inst.capacity[f] + TOL:
            errors.append(f"capacity of {f} exceeded in period {t}: {q} > {inst.capacity[f]}")
    for (s, t), q in by_st.items():
        if q > inst.demand[s][t] + TOL:
            errors.append(f"demand of {s} exceeded in period {t}: {q} > {inst.demand[s][t]}")
    opening = sum(inst.opening_costs[f] for f in start)
    if shipping + opening > inst.budget + TOL:
        errors.append(f"budget exceeded: {shipping + opening} > {inst.budget}")
    _check_totals(errors, sol, revenue, opening, shipping)
    return errors


def _check_totals(errors: List[str], sol: Solution, revenue: float, opening: float, shipping: float):
    for label, mine, theirs in (
        ("revenue", revenue, sol.total_revenue),
        ("opening cost", opening, sol.total_opening_cost),
        ("shipping cost", shipping, sol.total_shipping_cost),
    ):
        if abs(mine - theirs) > 1e-4:
            errors.append(f"reported {label} {theirs} != recomputed {mine}")


def verify(instance, solution) -> List[str]:
    """Return a list of constraint violations (empty list == solution is feasible)."""
    if isinstance(instance, StaticInstance):
        return verify_static(instance, solution)
    if isinstance(instance, SchedulingInstance):
        return verify_scheduling(instance, solution)
    raise TypeError(f"Unsupported instance type: {type(instance).__name__}")
