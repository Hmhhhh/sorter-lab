"""PLC-like scan-cycle logic, isolated from the physical process model."""

from __future__ import annotations

from dataclasses import dataclass

from .model import Faults, Inputs, MachineState, Outputs


@dataclass(slots=True)
class Controller:
    """A small deterministic state machine with a hardwired-style safety priority."""

    state: MachineState = MachineState.STOPPED
    outputs: Outputs | None = None
    sensor_high_scans: int = 0
    jam_scans: int = 0
    pending_divert_s: float = 0.0
    alarm_text: str = ""
    _start_armed: bool = True

    def __post_init__(self) -> None:
        if self.outputs is None:
            self.outputs = Outputs()

    def scan(self, inputs: Inputs, faults: Faults, dt_s: float) -> Outputs:
        """Evaluate inputs once and update outputs once, like a cyclic PLC task."""
        assert self.outputs is not None
        if inputs.emergency_stop:
            if self.state is not MachineState.E_STOP:
                self.alarm_text = "Emergency stop active — reset required"
            self.state = MachineState.E_STOP
            self.outputs = Outputs(alarm=True)
            return self.outputs

        if self.state is MachineState.E_STOP:
            # E-stop is latched: a separate stop/start sequence is required to reset.
            if inputs.stop:
                self.state = MachineState.STOPPED
                self.alarm_text = ""
            else:
                self.outputs = Outputs(alarm=True)
                return self.outputs

        self.sensor_high_scans = self.sensor_high_scans + 1 if inputs.sort_sensor else 0
        if self.sensor_high_scans >= 30:
            self.state = MachineState.FAULT
            self.alarm_text = "Sort sensor stuck high for 3.0 s"
        self.jam_scans = self.jam_scans + 1 if faults.conveyor_jam and self.state is MachineState.RUNNING else 0
        if self.jam_scans >= 20:
            self.state = MachineState.FAULT
            self.alarm_text = "Conveyor motion not detected for 2.0 s"

        if self.state is MachineState.FAULT:
            self.outputs = Outputs(alarm=True)
            if inputs.stop:
                self.state = MachineState.STOPPED
                self.alarm_text = ""
                self.sensor_high_scans = 0
                self.jam_scans = 0
                self.outputs = Outputs()
            return self.outputs

        if inputs.stop:
            self.state = MachineState.STOPPED
            self._start_armed = True
        elif inputs.start and self._start_armed and self.state is MachineState.STOPPED:
            self.state = MachineState.RUNNING
            self._start_armed = False

        if not inputs.start:
            self._start_armed = True

        if inputs.sort_sensor and self.state is MachineState.RUNNING:
            self.pending_divert_s = 0.7

        self.pending_divert_s = max(0.0, self.pending_divert_s - dt_s)
        self.outputs = Outputs(
            conveyor_motor=self.state is MachineState.RUNNING,
            diverter=(self.state is MachineState.RUNNING and self.pending_divert_s > 0),
            alarm=False,
        )
        if faults.diverter_failure:
            self.outputs.diverter = False
        return self.outputs
