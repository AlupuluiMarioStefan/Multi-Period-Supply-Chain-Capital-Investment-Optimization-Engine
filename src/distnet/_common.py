"""Small helpers shared by the solver modules."""

from __future__ import annotations

from typing import Optional

import pulp


def make_solver(msg: bool = False, time_limit: Optional[float] = None, gap: Optional[float] = None):
    """Build the default CBC solver (bundled with PuLP).

    ``time_limit`` is in seconds, ``gap`` is the relative MIP gap (e.g. ``0.01``).
    """
    kwargs = {"msg": msg}
    if time_limit is not None:
        kwargs["timeLimit"] = time_limit
    if gap is not None:
        kwargs["gapRel"] = gap
    return pulp.PULP_CBC_CMD(**kwargs)


def ival(var) -> int:
    """Integer value of a variable; removes solver noise such as 3.7e-13 or 249.9999999."""
    value = var.varValue
    return 0 if value is None else int(round(value))
