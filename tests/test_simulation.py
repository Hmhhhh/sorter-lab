from __future__ import annotations

import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parents[1] / "src"))

from sorter_lab.model import MachineState
from sorter_lab.simulation import SortingLine


class SimulationTests(unittest.TestCase):
    def test_seed_makes_runs_reproducible(self) -> None:
        runs = []
        for _ in range(2):
            line = SortingLine(seed=23)
            line.command("start")
            runs.append(line.step(500))
        self.assertEqual(runs[0]["bins"], runs[1]["bins"])
        self.assertEqual(runs[0]["metrics"], runs[1]["metrics"])

    def test_normal_run_routes_without_misclassification(self) -> None:
        line = SortingLine(seed=7)
        line.command("start")
        result = line.step(600)
        self.assertGreater(result["metrics"]["sorted_a"] + result["metrics"]["sorted_b"], 0)
        self.assertEqual(result["metrics"]["misrouted"], 0)
        self.assertEqual(result["metrics"]["accuracy_pct"], 100.0)

    def test_diverter_failure_is_visible_in_quality_metrics(self) -> None:
        line = SortingLine(seed=7)
        line.command("start")
        line.step(200)
        line.command("diverter_failure", True)
        result = line.step(400)
        self.assertGreater(result["metrics"]["misrouted"], 0)
        self.assertLess(result["metrics"]["accuracy_pct"], 100.0)

    def test_estop_stops_motor_and_counts_once(self) -> None:
        line = SortingLine()
        line.command("start")
        line.step(2)
        line.command("emergency_stop")
        result = line.step(1)
        self.assertEqual(result["state"], MachineState.E_STOP.value)
        self.assertFalse(result["outputs"]["conveyor_motor"])
        self.assertEqual(result["metrics"]["safety_trips"], 1)
        self.assertEqual(line.step(10)["metrics"]["safety_trips"], 1)

    def test_stopped_line_does_not_feed_parts(self) -> None:
        line = SortingLine()
        result = line.step(100)
        self.assertEqual(result["metrics"]["produced"], 0)
        self.assertEqual(result["parts"], [])

    def test_estop_requires_explicit_reset_before_restart(self) -> None:
        line = SortingLine()
        line.command("start")
        line.step(1)
        line.command("emergency_stop")
        line.step(1)
        line.command("reset_estop")
        self.assertEqual(line.step(1)["state"], MachineState.STOPPED.value)
        line.command("start")
        self.assertEqual(line.step(1)["state"], MachineState.RUNNING.value)


if __name__ == "__main__":
    unittest.main()
