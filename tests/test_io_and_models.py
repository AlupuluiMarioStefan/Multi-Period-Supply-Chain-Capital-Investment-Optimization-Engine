"""Loader, validation, crew assignment, verifier and CLI tests (fast, no heavy solves)."""

import contextlib
import copy
import io
import json
import tempfile
import unittest
from pathlib import Path

from distnet import InstanceError, load_instance, solve, verify
from distnet.cli import main
from distnet.io import load_static_files
from distnet.scheduling import assign_crews

DATA = Path(__file__).resolve().parent.parent / "data"


class Loading(unittest.TestCase):
    def test_text_directory(self):
        inst = load_instance(DATA / "level3_1")
        self.assertEqual(len(inst.facilities), 6)
        self.assertEqual(len(inst.service_areas), 10)
        self.assertEqual(inst.budget, 7000)
        self.assertEqual(inst.carrier_multiplier["C1"]["S3"], 0.8)

    def test_json_scheduling_seasonal_demand(self):
        inst = load_instance(DATA / "level5.json")
        self.assertEqual(len(inst.periods), 15)
        self.assertEqual(inst.demand["S1"][0], int(90 * 0.6))
        self.assertIn(("F1", "F2"), inst.dependencies)

    def test_eval_is_not_used(self):
        """File contents must never be executed (the original code used eval)."""
        with tempfile.TemporaryDirectory() as tmp:
            tmp = Path(tmp)
            (tmp / "f.txt").write_text("facility;capacity;opening_cost;shipping_costs\nF1;1;1;__import__('os').getcwd()\n")
            (tmp / "s.txt").write_text("service_area;demand;unit_selling_price\nS1;1;1\n")
            (tmp / "b.txt").write_text("budget\n10\n")
            with self.assertRaises(InstanceError):
                load_static_files(tmp / "f.txt", tmp / "s.txt", tmp / "b.txt")

    def test_missing_file(self):
        with self.assertRaises(FileNotFoundError):
            load_instance(DATA / "does_not_exist")


class Validation(unittest.TestCase):
    def test_missing_shipping_cost(self):
        inst = load_instance(DATA / "level2_1")
        del inst.unit_shipping_cost["F1"]["S3"]
        with self.assertRaises(InstanceError):
            inst.validate()

    def test_negative_demand(self):
        inst = load_instance(DATA / "level2_1")
        inst.demand["S1"] = -5
        with self.assertRaises(InstanceError):
            inst.validate()

    def test_carrier_unknown_area(self):
        inst = load_instance(DATA / "level3_1")
        inst.carrier_multiplier["C1"]["S99"] = 1.0
        with self.assertRaises(InstanceError):
            inst.validate()

    def test_bad_dependency(self):
        inst = load_instance(DATA / "level5.json")
        inst.dependencies.append(("F1", "F99"))
        with self.assertRaises(InstanceError):
            inst.validate()


class CrewAssignment(unittest.TestCase):
    def test_interval_colouring(self):
        starts = {"A": 0, "B": 0, "C": 2, "D": 3}
        durations = {"A": 2, "B": 3, "C": 1, "D": 2}
        assignment = assign_crews(starts, durations, ["K1", "K2"])
        for x in starts:
            for y in starts:
                if x < y and assignment[x] == assignment[y]:
                    self.assertTrue(
                        starts[x] + durations[x] <= starts[y] or starts[y] + durations[y] <= starts[x]
                    )

    def test_too_many_overlaps_raises(self):
        with self.assertRaises(RuntimeError):
            assign_crews({"A": 0, "B": 0}, {"A": 2, "B": 2}, ["K1"])


class Verifier(unittest.TestCase):
    def test_detects_capacity_violation(self):
        inst = load_instance(DATA / "level2_1")
        sol = solve(inst)
        bad = copy.deepcopy(sol)
        f, s, q = bad.allocations[0]
        bad.allocations[0] = (f, s, q + 10_000)
        self.assertTrue(verify(inst, bad))

    def test_detects_crew_overlap(self):
        inst = load_instance(DATA / "level4.json")
        sol = solve(inst)
        bad = copy.deepcopy(sol)
        # force every job onto the same crew
        bad.schedule = [(f, "K1", s, e) for f, _, s, e in bad.schedule]
        if len(bad.schedule) > 1:
            self.assertTrue(any("overlaps" in e for e in verify(inst, bad)))


class Cli(unittest.TestCase):
    def setUp(self):  # keep test output clean
        self._silence = contextlib.redirect_stdout(io.StringIO())
        self._silence.__enter__()

    def tearDown(self):
        self._silence.__exit__(None, None, None)

    def test_validate_command(self):
        self.assertEqual(main(["validate", str(DATA / "level1.json")]), 0)

    def test_bad_path_returns_error_code(self):
        self.assertEqual(main(["validate", str(DATA / "nope")]), 2)

    def test_solve_writes_outputs(self):
        with tempfile.TemporaryDirectory() as tmp:
            out_json, out_csv = Path(tmp) / "s.json", Path(tmp) / "s.csv"
            code = main(["solve", str(DATA / "level3_1"), "--json", str(out_json), "--csv", str(out_csv)])
            self.assertEqual(code, 0)
            data = json.loads(out_json.read_text())
            self.assertAlmostEqual(data["total_profit"], 23692.15, places=4)
            self.assertTrue(out_csv.read_text().startswith("facility,service_area,carrier,quantity"))


if __name__ == "__main__":
    unittest.main()
