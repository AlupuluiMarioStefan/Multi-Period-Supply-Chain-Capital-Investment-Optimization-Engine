"""End-to-end tests: every bundled instance must reach its known optimum and pass verification."""

import unittest
from pathlib import Path

from distnet import load_instance, solve, verify

DATA = Path(__file__).resolve().parent.parent / "data"

# Optimal profits, cross-checked against the original course scripts in legacy/.
EXPECTED = {
    "level1.json": 19792,
    "level2_1": 20729,
    "level2_2": 26604,
    "level3_1": 23692.15,
    "level3_2": 30807.15,
    "level4.json": 23160,
    "level5.json": 99169,
}


class BundledInstances(unittest.TestCase):
    def test_known_optima(self):
        for name, expected in EXPECTED.items():
            with self.subTest(instance=name):
                instance = load_instance(DATA / name)
                solution = solve(instance)
                self.assertTrue(solution.is_optimal)
                self.assertAlmostEqual(solution.total_profit, expected, places=4)
                self.assertEqual(verify(instance, solution), [])
                self.assertLessEqual(solution.budget_used, instance.budget + 1e-6)

    def test_quantities_are_clean_integers(self):
        """The original scripts leaked values like 3.7e-13 into the allocation plan."""
        solution = solve(load_instance(DATA / "level1.json"))
        for *_, qty in solution.allocations:
            self.assertIsInstance(qty, int)
            self.assertGreater(qty, 0)

    def test_allocation_tuple_shapes(self):
        static = solve(load_instance(DATA / "level2_1"))
        carriers = solve(load_instance(DATA / "level3_1"))
        sched = solve(load_instance(DATA / "level4.json"))
        self.assertTrue(all(len(a) == 3 for a in static.allocations))
        self.assertTrue(all(len(a) == 4 for a in carriers.allocations))
        self.assertTrue(all(len(a) == 4 for a in sched.allocations))
        self.assertTrue(all(len(s) == 4 for s in sched.schedule))


class FormulationVariants(unittest.TestCase):
    """The optimisations must never change the optimal value."""

    def test_static_variants_agree(self):
        instance = load_instance(DATA / "level3_1")
        base = solve(instance).total_profit
        for opts in ({"strengthen": False}, {"prune": False}, {"strengthen": False, "prune": False}):
            with self.subTest(**opts):
                self.assertAlmostEqual(solve(instance, **opts).total_profit, base, places=4)

    def test_scheduling_variants_agree(self):
        instance = load_instance(DATA / "level4.json")
        base = solve(instance).total_profit
        for opts in ({"crew_model": "indexed"}, {"strengthen": False}, {"prune": False}):
            with self.subTest(**opts):
                result = solve(instance, **opts)
                self.assertAlmostEqual(result.total_profit, base, places=4)
                self.assertEqual(verify(instance, result), [])


if __name__ == "__main__":
    unittest.main()
