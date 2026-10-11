"""Deterministic discrete-time process simulation for a tabletop sorting line."""

from __future__ import annotations

import random
from dataclasses import asdict

from .controller import Controller
from .model import Faults, Inputs, MachineState, Metrics, Part, Product


class SortingLine:
    """Simulate a sensor-triggered conveyor and pneumatic diverter.

    Geometry uses metres from the conveyor entry: sort sensor at 1.5 m,
    diverter at 2.0 m and exit at 3.0 m. The belt runs at 0.5 m/s.
    """

    DT_S = 0.1
    BELT_SPEED_M_S = 0.5
    SENSOR_M = 1.75
    DIVERTER_M = 2.0
    EXIT_M = 3.0
    SPAWN_INTERVAL_S = 2.5

    def __init__(self, seed: int = 7) -> None:
        self.random = random.Random(seed)
        self.seed = seed
        self.controller = Controller()
        self.inputs = Inputs()
        self.faults = Faults()
        self.metrics = Metrics()
        self.parts: list[Part] = []
        self.sorted_bins = {Product.A: 0, Product.B: 0}
        self.next_part_id = 1
        self.spawn_elapsed_s = 0.0
        self.now_s = 0.0
        self._sensor_was_high = False
        self._start_pulse = False
        self._stop_pulse = False
        self._estop_latched = False
        self._was_estopped = False
        self._log: list[dict[str, object]] = []

    def command(self, action: str, enabled: bool | None = None) -> None:
        """Set operator controls or inject/remove a named fault."""
        if action == "start":
            self._start_pulse = True
        elif action == "stop":
            self._stop_pulse = True
        elif action in {"emergency_stop", "estop"}:
            self._estop_latched = True if enabled is None else enabled
        elif action == "reset_estop":
            if not self._estop_latched and self.controller.state is not MachineState.E_STOP:
                raise ValueError("Emergency stop is not active")
            self._estop_latched = False
            self._stop_pulse = True
        elif action in {"sensor_stuck_on", "conveyor_jam", "diverter_failure"}:
            setattr(self.faults, action, True if enabled is None else enabled)
        else:
            raise ValueError(f"Unknown action: {action}")

    def step(self, cycles: int = 1) -> dict[str, object]:
        if cycles < 1:
            raise ValueError("cycles must be at least 1")
        for _ in range(cycles):
            self._step_once()
        return self.snapshot()

    def run_for(self, seconds: float, auto_start: bool = True) -> dict[str, object]:
        if seconds < 0:
            raise ValueError("seconds must be non-negative")
        if auto_start and self.controller.state is MachineState.STOPPED:
            self.command("start")
        cycles = round(seconds / self.DT_S)
        return self.step(max(1, cycles)) if cycles else self.snapshot()

    def _step_once(self) -> None:
        dt = self.DT_S
        self.now_s += dt
        self.metrics.elapsed_s += dt
        output = self.controller.outputs
        self.inputs = Inputs(
            start=self._start_pulse,
            stop=self._stop_pulse,
            emergency_stop=self._estop_latched,
            entry_sensor=any(p.position_m < 0.2 for p in self.parts),
            sort_sensor=(any(abs(p.position_m - self.SENSOR_M) < 0.04 for p in self.parts)
                         or self.faults.sensor_stuck_on),
            exit_sensor=any(abs(p.position_m - self.EXIT_M) < 0.04 for p in self.parts),
        )
        previous_state = self.controller.state
        output = self.controller.scan(self.inputs, self.faults, dt)
        if output.conveyor_motor:
            self.spawn_elapsed_s += dt
            if self.spawn_elapsed_s + 1e-9 >= self.SPAWN_INTERVAL_S:
                self.spawn_elapsed_s -= self.SPAWN_INTERVAL_S
                self.parts.append(Part(self.next_part_id, self.random.choice(list(Product)),
                                       created_at_s=self.now_s))
                self.next_part_id += 1
                self.metrics.produced += 1
        if self.controller.state is MachineState.FAULT and previous_state is not MachineState.FAULT:
            self._log.append({"time_s": round(self.now_s, 1), "event": self.controller.alarm_text})
        if self.controller.state is MachineState.E_STOP and not self._was_estopped:
            self.metrics.safety_trips += 1
            self._log.append({"time_s": round(self.now_s, 1), "event": "Emergency stop"})
        self._was_estopped = self.controller.state is MachineState.E_STOP

        if output.conveyor_motor and not self.faults.conveyor_jam:
            for part in self.parts:
                part.position_m += self.BELT_SPEED_M_S * dt

        sensor_high = self.inputs.sort_sensor and not self.faults.sensor_stuck_on
        if sensor_high and not self._sensor_was_high:
            # The product is identified at the sensor; only product A is diverted.
            for part in self.parts:
                if abs(part.position_m - self.SENSOR_M) < 0.08 and part.product is Product.A:
                    part.diverted = True
                    break
        self._sensor_was_high = self.inputs.sort_sensor

        remaining: list[Part] = []
        for part in self.parts:
            if part.position_m >= self.DIVERTER_M and part.diverted:
                if self.faults.diverter_failure or not output.diverter:
                    self.sorted_bins[Product.B] += 1
                    self.metrics.sorted_b += 1
                    self.metrics.misrouted += 1
                    self._log.append({"time_s": round(self.now_s, 1), "event": "misroute",
                                      "part": part.part_id, "expected": "A", "actual": "B"})
                else:
                    self.sorted_bins[Product.A] += 1
                    self.metrics.sorted_a += 1
                self.metrics.cycle_times_s.append(self.now_s - part.created_at_s)
                continue
            if part.position_m >= self.EXIT_M:
                self.sorted_bins[part.product] += 1
                if part.product is Product.A:
                    self.metrics.sorted_a += 1
                else:
                    self.metrics.sorted_b += 1
                self.metrics.cycle_times_s.append(self.now_s - part.created_at_s)
                continue
            remaining.append(part)
        self.parts = remaining
        self._start_pulse = False
        self._stop_pulse = False

    def snapshot(self) -> dict[str, object]:
        output = self.controller.outputs
        cycle_times = self.metrics.cycle_times_s
        metrics = asdict(self.metrics)
        metrics.pop("cycle_times_s")
        metrics.update({
            "throughput_per_min": round(self.metrics.throughput_per_min, 2),
            "accuracy_pct": round(self.metrics.accuracy_pct, 2),
            "average_cycle_time_s": round(sum(cycle_times) / len(cycle_times), 2) if cycle_times else 0.0,
        })
        return {
            "time_s": round(self.now_s, 1),
            "seed": self.seed,
            "state": self.controller.state.value,
            "alarm": self.controller.alarm_text,
            "inputs": asdict(self.inputs),
            "outputs": asdict(output) if output else {},
            "faults": asdict(self.faults),
            "parts": [{"id": p.part_id, "product": p.product.value,
                       "position_m": round(p.position_m, 2), "diverted": p.diverted}
                      for p in self.parts],
            "bins": {key.value: value for key, value in self.sorted_bins.items()},
            "metrics": metrics,
            "events": self._log[-12:],
        }
