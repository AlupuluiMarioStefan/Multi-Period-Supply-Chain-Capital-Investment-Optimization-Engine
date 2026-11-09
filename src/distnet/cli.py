"""Command line interface: ``distnet solve <instance>``."""

from __future__ import annotations

import argparse
import json
import sys
import time

from . import __version__
from .io import load_instance, solution_to_dict, write_allocations_csv
from .models import InstanceError, SchedulingInstance
from .report import format_report


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(
        prog="distnet", description="Profit-maximising distribution network optimiser (PuLP/CBC)."
    )
    p.add_argument("--version", action="version", version=f"distnet {__version__}")
    sub = p.add_subparsers(dest="command", required=True)

    s = sub.add_parser("solve", help="solve an instance and print a report")
    s.add_argument("instance", help="a .json file or a directory with facilities.txt, ...")
    s.add_argument("--time-limit", type=float, metavar="SEC", help="solver time limit in seconds")
    s.add_argument("--gap", type=float, metavar="REL", help="relative MIP gap, e.g. 0.01")
    s.add_argument("--no-strengthen", action="store_true", help="omit the valid linking inequalities")
    s.add_argument("--no-prune", action="store_true", help="keep unprofitable variables")
    s.add_argument("--crew-model", choices=["aggregated", "indexed"], default="aggregated",
                   help="scheduling instances only (default: aggregated)")
    s.add_argument("--json", metavar="FILE", help="write the full solution as JSON")
    s.add_argument("--csv", metavar="FILE", help="write the allocation plan as CSV")
    s.add_argument("--solver-log", action="store_true", help="show the CBC log")
    s.add_argument("--max-rows", type=int, default=40, help="allocation rows printed (default 40)")

    v = sub.add_parser("validate", help="check that an instance file is well-formed")
    v.add_argument("instance")
    return p


def main(argv=None) -> int:
    args = build_parser().parse_args(argv)
    try:
        instance = load_instance(args.instance)
    except (InstanceError, FileNotFoundError, ValueError) as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 2

    if args.command == "validate":
        kind = "scheduling" if isinstance(instance, SchedulingInstance) else "static"
        print(f"OK: {kind} instance with {len(instance.facilities)} facilities "
              f"and {len(instance.service_areas)} service areas")
        return 0

    from . import solve  # imported lazily so `validate` works without a solver
    from .verify import verify

    options = dict(
        strengthen=not args.no_strengthen, prune=not args.no_prune,
        time_limit=args.time_limit, gap=args.gap, msg=args.solver_log,
    )
    if isinstance(instance, SchedulingInstance):
        options["crew_model"] = args.crew_model
    started = time.perf_counter()
    solution = solve(instance, **options)
    elapsed = time.perf_counter() - started

    print(format_report(instance, solution, max_allocations=args.max_rows))
    errors = verify(instance, solution)
    print(f"\nIndependent verification: {'PASSED' if not errors else 'FAILED'}  (solved in {elapsed:.2f}s)")
    for e in errors:
        print(f"  - {e}")
    if args.json:
        with open(args.json, "w", encoding="utf-8") as fh:
            json.dump(solution_to_dict(solution), fh, indent=2)
    if args.csv:
        write_allocations_csv(solution, args.csv)
    return 0 if solution.is_optimal and not errors else 1


if __name__ == "__main__":
    sys.exit(main())
