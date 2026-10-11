"""Domain model for the sorting-line digital twin."""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import StrEnum


class Product(StrEnum):
    A = "A"
    B = "B"


class MachineState(StrEnum):
    STOPPED = "stopped"
    RUNNING = "running"
    E_STOP = "e_stop"
    FAULT = "fault"


@dataclass(slots=True)
class Part:
    part_id: int
    product: Product
    position_m: float = 0.0
    diverted: bool = False
    created_at_s: float = 0.0


@dataclass(slots=True)
class Inputs:
    start: bool = False
    stop: bool = False
    emergency_stop: bool = False
    entry_sensor: bool = False
    sort_sensor: bool = False
    exit_sensor: bool = False


@dataclass(slots=True)
class Outputs:
    conveyor_motor: bool = False
    diverter: bool = False
    alarm: bool = False


@dataclass(slots=True)
class Faults:
    sensor_stuck_on: bool = False
    conveyor_jam: bool = False
    diverter_failure: bool = False


@dataclass(slots=True)
class Metrics:
    produced: int = 0
    sorted_a: int = 0
    sorted_b: int = 0
    rejected: int = 0
    misrouted: int = 0
    safety_trips: int = 0
    elapsed_s: float = 0.0
    cycle_times_s: list[float] = field(default_factory=list)

    @property
    def throughput_per_min(self) -> float:
        if self.elapsed_s <= 0:
            return 0.0
        return (self.sorted_a + self.sorted_b + self.rejected) * 60.0 / self.elapsed_s

    @property
    def accuracy_pct(self) -> float:
        total = self.sorted_a + self.sorted_b
        return 100.0 if total == 0 else 100.0 * (total - self.misrouted) / total
