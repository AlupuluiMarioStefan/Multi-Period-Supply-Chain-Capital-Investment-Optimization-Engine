"""Minimal example of the Python API.  Run from the repository root:

    python examples/basic_usage.py
"""

from distnet import format_report, load_instance, solve, verify

instance = load_instance("data/level3_1")      # a directory of text files ...
# instance = load_instance("data/level5.json")  # ... or a JSON file

solution = solve(instance, time_limit=60)       # options: strengthen, prune, gap, msg, ...
print(format_report(instance, solution))

assert verify(instance, solution) == [], "solution violates a constraint"
print(f"\nProfit: {solution.total_profit:,.2f}")
