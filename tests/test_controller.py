from __future__ import annotations

import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parents[1] / "src"))

from sorter_lab.controller import Controller
from sorter_lab.model import Faults, Inputs, MachineState


class ControllerTests(unittest.TestCase):
    def test_emergency_stop_has_priority_and_latches(self) -> None:
        plc = Controller(state=MachineState.RUNNING)
        output = plc.scan(Inputs(emergency_stop=True), Faults(), 0.1)
        self.assertFalse(output.conveyor_motor)
        self.assertFalse(output.diverter)
        self.assertTrue(output.alarm)
        self.assertEqual(plc.state, MachineState.E_STOP)

        plc.scan(Inputs(), Faults(), 0.1)
        self.assertEqual(plc.state, MachineState.E_STOP)

    def test_stuck_sensor_enters_safe_fault_state(self) -> None:
        plc = Controller(state=MachineState.RUNNING)
        for _ in range(30):
            output = plc.scan(Inputs(sort_sensor=True), Faults(), 0.1)
        self.assertEqual(plc.state, MachineState.FAULT)
        self.assertFalse(output.conveyor_motor)
        self.assertTrue(output.alarm)

    def test_conveyor_jam_is_detected(self) -> None:
        plc = Controller(state=MachineState.RUNNING)
        for _ in range(20):
            output = plc.scan(Inputs(), Faults(conveyor_jam=True), 0.1)
        self.assertEqual(plc.state, MachineState.FAULT)
        self.assertFalse(output.conveyor_motor)


if __name__ == "__main__":
    unittest.main()
