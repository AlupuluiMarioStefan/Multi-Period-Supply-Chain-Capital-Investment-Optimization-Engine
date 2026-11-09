"""Human-readable text report for solutions."""

from __future__ import annotations

from typing import List

from .models import SchedulingInstance, SchedulingSolution, Solution, StaticSolution


def _money(x: float) -> str:
    return f"{x:,.2f}".rstrip("0").rstrip(".") if abs(x - round(x)) > 1e-9 else f"{int(round(x)):,}"


def _gantt(instance: SchedulingInstance, sol: SchedulingSolution) -> List[str]:
    width = max(4, max((len(f) for f in instance.facilities), default=2) + 1)
    lines = ["    " + "".join(str(t).ljust(width) for t in instance.periods)]
    for c in instance.crews:
        cells = []
        for t in instance.periods:
            job = next((f for f, crew, s0, e0 in sol.schedule if crew == c and s0 <= t < e0), None)
            cells.append((job or ".").ljust(width))
        lines.append(f"{c:<4}" + "".join(cells))
    return lines


def format_report(instance, sol: Solution, max_allocations: int = 40) -> str:
    """Render a solution as text. ``max_allocations`` caps the printed allocation rows."""
    out: List[str] = []
    out.append(f"Status:          {sol.status}")
    out.append(f"Total profit:    {_money(sol.total_profit)}")
    out.append(
        f"  revenue {_money(sol.total_revenue)} - opening {_money(sol.total_opening_cost)}"
        f" - shipping {_money(sol.total_shipping_cost)}"
    )
    pct = 100 * sol.budget_used / sol.budget if sol.budget else 0
    out.append(f"Budget used:     {_money(sol.budget_used)} / {_money(sol.budget)} ({pct:.2f}%)")
    out.append(f"Facilities open: {', '.join(sol.facilities_opened) or '-'}")
    closed = [f for f in instance.facilities if f not in sol.facilities_opened]
    out.append(f"Facilities shut: {', '.join(closed) or '-'}")

    if isinstance(sol, StaticSolution) and sol.volume_used:
        out.append("\nCarrier volume:")
        for c, used in sol.volume_used.items():
            cap = instance.max_volume[c]
            out.append(f"  {c}: {used} / {cap} (remaining {cap - used})")

    if isinstance(sol, SchedulingSolution):
        out.append("\nConstruction schedule (facility, crew, start -> completed):")
        for f, c, s0, e0 in sol.schedule:
            out.append(f"  {f}: {c}, period {s0} -> {e0}")
        if instance.dependencies:
            out.append("Dependencies:")
            for first, second in instance.dependencies:
                if second in sol.facilities_opened:
                    done = next(e for f, _, _, e in sol.schedule if f == first)
                    begin = next(s for f, _, s, _ in sol.schedule if f == second)
                    out.append(f"  {first} done at {done}, {second} starts at {begin}: OK")
                else:
                    out.append(f"  {second} not built (requires {first}): OK")
        out.append("\nCrew timeline (. = idle):")
        out.extend("  " + line for line in _gantt(instance, sol))

    total_met = sum(sol.demand_met.values())
    total = total_met + sum(sol.demand_unmet.values())
    out.append(f"\nDemand met: {total_met} / {total} ({100 * total_met / total if total else 0:.1f}%)")
    for s in instance.service_areas:
        met, unmet = sol.demand_met[s], sol.demand_unmet[s]
        out.append(f"  {s}: met {met} of {met + unmet} (unmet {unmet})")

    out.append(f"\nAllocation plan ({len(sol.allocations)} shipments):")
    for row in sol.allocations[:max_allocations]:
        out.append("  " + " -> ".join(str(x) for x in row[:-1]) + f" : {row[-1]}")
    if len(sol.allocations) > max_allocations:
        out.append(f"  ... {len(sol.allocations) - max_allocations} more (use --csv to export all)")
    return "\n".join(out)
