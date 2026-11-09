"""Problem instances and solution containers (plain dataclasses, no solver imports)."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Dict, List, Mapping, Sequence, Tuple


class InstanceError(ValueError):
    """Raised when an instance is incomplete or inconsistent."""


def _require_keys(label: str, mapping: Mapping, keys: Sequence) -> None:
    missing = [k for k in keys if k not in mapping]
    if missing:
        raise InstanceError(f"{label} is missing entries for: {', '.join(map(str, missing))}")


def _require_non_negative(label: str, mapping: Mapping) -> None:
    bad = [k for k, v in mapping.items() if v < 0]
    if bad:
        raise InstanceError(f"{label} must be non-negative (offending: {', '.join(map(str, bad))})")


def _require_unique(label: str, items: Sequence) -> None:
    if len(set(items)) != len(items):
        raise InstanceError(f"{label} contains duplicates")


# --------------------------------------------------------------------------- #
# Instances
# --------------------------------------------------------------------------- #
@dataclass
class StaticInstance:
    """Single-period facility location + allocation problem (levels 1-3).

    If ``carriers`` is empty, shipping is direct at the base unit cost. Otherwise
    each carrier serves a subset of service areas at ``multiplier * base cost`` and
    has a total volume limit.
    """

    facilities: List[str]
    service_areas: List[str]
    capacity: Dict[str, int]
    opening_costs: Dict[str, float]
    demand: Dict[str, int]
    unit_selling_price: Dict[str, float]
    unit_shipping_cost: Dict[str, Dict[str, float]]
    budget: float
    carriers: List[str] = field(default_factory=list)
    max_volume: Dict[str, int] = field(default_factory=dict)
    carrier_multiplier: Dict[str, Dict[str, float]] = field(default_factory=dict)

    def validate(self) -> None:
        _require_unique("facilities", self.facilities)
        _require_unique("service_areas", self.service_areas)
        _require_keys("capacity", self.capacity, self.facilities)
        _require_keys("opening_costs", self.opening_costs, self.facilities)
        _require_keys("unit_shipping_cost", self.unit_shipping_cost, self.facilities)
        _require_keys("demand", self.demand, self.service_areas)
        _require_keys("unit_selling_price", self.unit_selling_price, self.service_areas)
        for f in self.facilities:
            _require_keys(f"unit_shipping_cost[{f}]", self.unit_shipping_cost[f], self.service_areas)
        for label, m in (("capacity", self.capacity), ("opening_costs", self.opening_costs),
                         ("demand", self.demand), ("unit_selling_price", self.unit_selling_price)):
            _require_non_negative(label, m)
        if self.budget < 0:
            raise InstanceError("budget must be non-negative")
        if self.carriers:
            _require_unique("carriers", self.carriers)
            _require_keys("max_volume", self.max_volume, self.carriers)
            _require_keys("carrier_multiplier", self.carrier_multiplier, self.carriers)
            _require_non_negative("max_volume", self.max_volume)
            for c in self.carriers:
                unknown = [s for s in self.carrier_multiplier[c] if s not in self.service_areas]
                if unknown:
                    raise InstanceError(f"carrier {c} references unknown service areas: {unknown}")
                _require_non_negative(f"carrier_multiplier[{c}]", self.carrier_multiplier[c])


@dataclass
class SchedulingInstance:
    """Multi-period problem with construction scheduling (levels 4-5).

    Facilities must be *built* by a crew (``build_time`` periods, one facility per crew
    at a time) before they can ship. Shipping happens in periods ``start + build_time``
    onwards. ``dependencies`` are ``(first, second)`` pairs: ``second`` may only be
    built if ``first`` is built and completed before ``second`` starts.
    """

    facilities: List[str]
    service_areas: List[str]
    periods: List[int]
    crews: List[str]
    capacity: Dict[str, int]  # per period
    opening_costs: Dict[str, float]
    build_time: Dict[str, int]
    demand: Dict[str, Dict[int, int]]  # demand[s][t]
    unit_selling_price: Dict[str, float]
    unit_shipping_cost: Dict[str, Dict[str, float]]
    budget: float
    dependencies: List[Tuple[str, str]] = field(default_factory=list)

    def validate(self) -> None:
        _require_unique("facilities", self.facilities)
        _require_unique("service_areas", self.service_areas)
        _require_unique("crews", self.crews)
        if not self.periods or self.periods != list(range(len(self.periods))):
            raise InstanceError("periods must be the consecutive integers 0..T-1")
        _require_keys("capacity", self.capacity, self.facilities)
        _require_keys("opening_costs", self.opening_costs, self.facilities)
        _require_keys("build_time", self.build_time, self.facilities)
        _require_keys("unit_shipping_cost", self.unit_shipping_cost, self.facilities)
        _require_keys("demand", self.demand, self.service_areas)
        _require_keys("unit_selling_price", self.unit_selling_price, self.service_areas)
        for f in self.facilities:
            _require_keys(f"unit_shipping_cost[{f}]", self.unit_shipping_cost[f], self.service_areas)
            if int(self.build_time[f]) != self.build_time[f] or self.build_time[f] < 1:
                raise InstanceError(f"build_time[{f}] must be a positive integer")
        for s in self.service_areas:
            _require_keys(f"demand[{s}]", self.demand[s], self.periods)
            _require_non_negative(f"demand[{s}]", self.demand[s])
        for label, m in (("capacity", self.capacity), ("opening_costs", self.opening_costs),
                         ("unit_selling_price", self.unit_selling_price)):
            _require_non_negative(label, m)
        if self.budget < 0:
            raise InstanceError("budget must be non-negative")
        for first, second in self.dependencies:
            if first not in self.facilities or second not in self.facilities:
                raise InstanceError(f"dependency ({first}, {second}) references an unknown facility")
            if first == second:
                raise InstanceError(f"facility {first} cannot depend on itself")


# --------------------------------------------------------------------------- #
# Solutions
# --------------------------------------------------------------------------- #
@dataclass
class Solution:
    """Result common to all problem types. All quantities are rounded integers."""

    status: str
    budget: float
    total_revenue: float
    total_opening_cost: float
    total_shipping_cost: float
    facilities_opened: List[str]
    demand_met: Dict[str, int]
    demand_unmet: Dict[str, int]
    allocations: List[tuple]

    @property
    def is_optimal(self) -> bool:
        return self.status == "Optimal"

    @property
    def total_profit(self) -> float:
        return self.total_revenue - self.total_opening_cost - self.total_shipping_cost

    @property
    def budget_used(self) -> float:
        return self.total_opening_cost + self.total_shipping_cost


@dataclass
class StaticSolution(Solution):
    """``allocations`` are ``(facility, area, qty)`` or ``(facility, area, carrier, qty)``."""

    volume_used: Dict[str, int] = field(default_factory=dict)  # per carrier


@dataclass
class SchedulingSolution(Solution):
    """``allocations`` are ``(facility, area, period, qty)``."""

    schedule: List[Tuple[str, str, int, int]] = field(default_factory=list)  # (f, crew, start, end)
    crew_usage: Dict[str, List[int]] = field(default_factory=dict)  # crew -> 0/1 per period
