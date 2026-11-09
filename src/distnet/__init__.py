"""distnet - profit-maximising distribution network design with PuLP.

Quick start::

    from distnet import load_instance, solve
    instance = load_instance("data/level3_1")
    solution = solve(instance)
    print(solution.total_profit)
"""

from .io import load_instance, load_static_files, solution_to_dict
from .models import (
    InstanceError,
    SchedulingInstance,
    SchedulingSolution,
    Solution,
    StaticInstance,
    StaticSolution,
)
from .report import format_report
from .scheduling import solve_scheduling
from .static import solve_static
from .verify import verify

__version__ = "1.0.0"


def solve(instance, **options):
    """Solve any supported instance; dispatches on the instance type."""
    if isinstance(instance, StaticInstance):
        return solve_static(instance, **options)
    if isinstance(instance, SchedulingInstance):
        return solve_scheduling(instance, **options)
    raise TypeError(f"Unsupported instance type: {type(instance).__name__}")


__all__ = [
    "InstanceError",
    "SchedulingInstance",
    "SchedulingSolution",
    "Solution",
    "StaticInstance",
    "StaticSolution",
    "format_report",
    "load_instance",
    "load_static_files",
    "solution_to_dict",
    "solve",
    "solve_scheduling",
    "solve_static",
    "verify",
]
