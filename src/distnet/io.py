"""Reading instances (semicolon text files or JSON) and writing solutions."""

from __future__ import annotations

import ast
import csv
import json
from dataclasses import asdict
from pathlib import Path
from typing import Optional, Union

from .models import InstanceError, SchedulingInstance, SchedulingSolution, Solution, StaticInstance

PathLike = Union[str, Path]


def _number(text: str):
    """Parse '450' -> 450 and '0.85' -> 0.85."""
    value = float(text)
    return int(value) if value.is_integer() else value


def _rows(path: PathLike, ncols: int):
    """Yield the data rows of a ';'-separated file with a header line."""
    with open(path, newline="", encoding="utf-8") as fh:
        lines = [ln.strip() for ln in fh if ln.strip()]
    for n, line in enumerate(lines[1:], start=2):
        parts = [p.strip() for p in line.split(";", ncols - 1)]
        if len(parts) != ncols:
            raise InstanceError(f"{path}:{n}: expected {ncols} ';'-separated columns")
        yield parts


def _literal(text: str, path: PathLike):
    try:
        return ast.literal_eval(text)  # safe: literals only, unlike eval()
    except (ValueError, SyntaxError) as exc:
        raise InstanceError(f"{path}: cannot parse {text[:40]!r}: {exc}") from exc


# --------------------------------------------------------------------------- #
# Text-file format (levels 2-3)
# --------------------------------------------------------------------------- #
def load_static_files(
    facility_file: PathLike,
    service_area_file: PathLike,
    budget_file: PathLike,
    carrier_file: Optional[PathLike] = None,
) -> StaticInstance:
    """Load a static instance from the course's semicolon-separated text files."""
    with open(budget_file, encoding="utf-8") as fh:
        lines = [ln.strip() for ln in fh if ln.strip()]
    if len(lines) < 2:
        raise InstanceError(f"{budget_file}: expected a header line followed by the budget")
    budget = _number(lines[1])

    facilities, capacity, opening, shipping = [], {}, {}, {}
    for f, cap, cost, ship in _rows(facility_file, 4):
        facilities.append(f)
        capacity[f] = _number(cap)
        opening[f] = _number(cost)
        shipping[f] = _literal(ship, facility_file)

    areas, demand, price = [], {}, {}
    for s, dem, pr in _rows(service_area_file, 3):
        areas.append(s)
        demand[s] = _number(dem)
        price[s] = _number(pr)

    carriers, max_volume, multiplier = [], {}, {}
    if carrier_file is not None:
        for c, vol, mult in _rows(carrier_file, 3):
            carriers.append(c)
            max_volume[c] = _number(vol)
            multiplier[c] = {s: m for s, m in _literal(mult, carrier_file)}

    instance = StaticInstance(
        facilities=facilities, service_areas=areas, capacity=capacity, opening_costs=opening,
        demand=demand, unit_selling_price=price, unit_shipping_cost=shipping, budget=budget,
        carriers=carriers, max_volume=max_volume, carrier_multiplier=multiplier,
    )
    instance.validate()
    return instance


def _load_directory(path: Path) -> StaticInstance:
    carriers = path / "carriers.txt"
    return load_static_files(
        path / "facilities.txt", path / "service_areas.txt", path / "budget.txt",
        carriers if carriers.exists() else None,
    )


# --------------------------------------------------------------------------- #
# JSON format (all levels)
# --------------------------------------------------------------------------- #
def _load_json_static(d: dict) -> StaticInstance:
    fac, areas = d["facilities"], d["service_areas"]
    carriers = d.get("carriers", {})
    return StaticInstance(
        facilities=list(fac), service_areas=list(areas),
        capacity={f: v["capacity"] for f, v in fac.items()},
        opening_costs={f: v["opening_cost"] for f, v in fac.items()},
        unit_shipping_cost={f: dict(v["shipping_cost"]) for f, v in fac.items()},
        demand={s: v["demand"] for s, v in areas.items()},
        unit_selling_price={s: v["price"] for s, v in areas.items()},
        budget=d["budget"],
        carriers=list(carriers),
        max_volume={c: v["max_volume"] for c, v in carriers.items()},
        carrier_multiplier={c: dict(v["multipliers"]) for c, v in carriers.items()},
    )


def _load_json_scheduling(d: dict) -> SchedulingInstance:
    fac, areas = d["facilities"], d["service_areas"]
    horizon = d["horizon"]
    periods = list(range(horizon))
    factors = d.get("seasonal_factors")
    if factors is not None and len(factors) != horizon:
        raise InstanceError("seasonal_factors must have one entry per period")
    demand = {}
    for s, v in areas.items():
        spec = v["demand"]
        if isinstance(spec, list):
            if len(spec) != horizon:
                raise InstanceError(f"demand list of {s} must have {horizon} entries")
            demand[s] = {t: spec[t] for t in periods}
        else:  # base demand, optionally scaled by the seasonal factor of each period
            demand[s] = {t: int(spec * (factors[t] if factors else 1)) for t in periods}
    return SchedulingInstance(
        facilities=list(fac), service_areas=list(areas), periods=periods, crews=list(d["crews"]),
        capacity={f: v["capacity"] for f, v in fac.items()},
        opening_costs={f: v["opening_cost"] for f, v in fac.items()},
        build_time={f: v["build_time"] for f, v in fac.items()},
        unit_shipping_cost={f: dict(v["shipping_cost"]) for f, v in fac.items()},
        demand=demand,
        unit_selling_price={s: v["price"] for s, v in areas.items()},
        budget=d["budget"],
        dependencies=[tuple(p) for p in d.get("dependencies", [])],
    )


def load_instance(path: PathLike) -> Union[StaticInstance, SchedulingInstance]:
    """Load an instance from a ``.json`` file or from a directory of text files.

    A directory must contain ``facilities.txt``, ``service_areas.txt`` and ``budget.txt``
    and may contain ``carriers.txt``.
    """
    path = Path(path)
    if not path.exists():
        raise FileNotFoundError(path)
    if path.is_dir():
        return _load_directory(path)
    with open(path, encoding="utf-8") as fh:
        data = json.load(fh)
    kind = data.get("type", "static")
    try:
        if kind == "static":
            instance = _load_json_static(data)
        elif kind == "scheduling":
            instance = _load_json_scheduling(data)
        else:
            raise InstanceError(f"{path}: unknown instance type {kind!r}")
    except KeyError as exc:
        raise InstanceError(f"{path}: missing field {exc}") from exc
    instance.validate()
    return instance


# --------------------------------------------------------------------------- #
# Output
# --------------------------------------------------------------------------- #
def solution_to_dict(solution: Solution) -> dict:
    """JSON-serialisable representation of a solution (including derived totals)."""
    data = asdict(solution)
    data["total_profit"] = solution.total_profit
    data["budget_used"] = solution.budget_used
    data["is_optimal"] = solution.is_optimal
    data["kind"] = "scheduling" if isinstance(solution, SchedulingSolution) else "static"
    return data


def write_allocations_csv(solution: Solution, path: PathLike) -> None:
    """Write the allocation plan as CSV (columns depend on the problem type)."""
    if isinstance(solution, SchedulingSolution):
        header = ["facility", "service_area", "period", "quantity"]
    elif solution.allocations and len(solution.allocations[0]) == 4:
        header = ["facility", "service_area", "carrier", "quantity"]
    else:
        header = ["facility", "service_area", "quantity"]
    with open(path, "w", newline="", encoding="utf-8") as fh:
        writer = csv.writer(fh)
        writer.writerow(header)
        writer.writerows(solution.allocations)
