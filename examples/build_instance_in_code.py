"""Build a tiny instance directly in Python instead of loading files."""

from distnet import StaticInstance, format_report, solve

instance = StaticInstance(
    facilities=["North", "South"],
    service_areas=["A", "B", "C"],
    capacity={"North": 100, "South": 80},
    opening_costs={"North": 300, "South": 150},
    demand={"A": 60, "B": 50, "C": 70},
    unit_selling_price={"A": 20, "B": 18, "C": 15},
    unit_shipping_cost={
        "North": {"A": 4, "B": 6, "C": 3},
        "South": {"A": 7, "B": 2, "C": 5},
    },
    budget=1200,
)
print(format_report(instance, solve(instance)))
