"""Command-line interface for the Sorter Lab digital twin."""

from __future__ import annotations

import argparse
import csv
import json
from pathlib import Path

from .simulation import SortingLine
from .web import serve


def main() -> None:
    parser = argparse.ArgumentParser(prog="sorter-lab", description="PLC sorting-line digital twin")
    sub = parser.add_subparsers(dest="command", required=True)
    web = sub.add_parser("web", help="start the live browser dashboard")
    web.add_argument("--host", default="127.0.0.1")
    web.add_argument("--port", type=int, default=8765)
    web.add_argument("--seed", type=int, default=7)
    sim = sub.add_parser("simulate", help="run a reproducible headless simulation")
    sim.add_argument("--seconds", type=float, default=60)
    sim.add_argument("--seed", type=int, default=7)
    sim.add_argument("--fault", choices=["sensor_stuck_on", "conveyor_jam", "diverter_failure"])
    sim.add_argument("--fault-at", type=float, default=10, help="fault injection time in seconds")
    sim.add_argument("--csv", type=Path, help="write a 0.5 s KPI trace to this CSV file")
    args = parser.parse_args()

    if args.command == "web":
        serve(args.host, args.port, args.seed)
        return

    line = SortingLine(seed=args.seed)
    if args.seconds < 0:
        parser.error("--seconds must be non-negative")
    if args.fault and not 0 <= args.fault_at <= args.seconds:
        parser.error("--fault-at must be between 0 and --seconds when --fault is used")
    line.command("start")
    total_cycles = round(args.seconds / line.DT_S)
    fault_cycles = max(0, round(args.fault_at / line.DT_S))
    trace = [line.snapshot()]
    completed = 0
    fault_injected = False
    while completed < total_cycles:
        if args.fault and not fault_injected and completed >= fault_cycles:
            line.command(args.fault, True)
            fault_injected = True
        next_boundary = min(total_cycles, completed + 5)
        if args.fault and not fault_injected and fault_cycles < next_boundary:
            next_boundary = max(completed + 1, fault_cycles)
        line.step(next_boundary - completed)
        completed = next_boundary
        trace.append(line.snapshot())
    if args.fault and not fault_injected:
        line.command(args.fault, True)
    print(json.dumps(line.snapshot(), ensure_ascii=False, indent=2))
    if args.csv:
        columns = ["time_s", "state", "produced", "sorted_a", "sorted_b", "misrouted",
                   "throughput_per_min", "accuracy_pct", "average_cycle_time_s"]
        with args.csv.open("w", newline="", encoding="utf-8-sig") as stream:
            writer = csv.DictWriter(stream, fieldnames=columns)
            writer.writeheader()
            for sample in trace:
                writer.writerow({"time_s": sample["time_s"], "state": sample["state"],
                                 **{name: sample["metrics"][name] for name in columns[2:]}})
        print(f"CSV trace written to {args.csv}")


if __name__ == "__main__":
    main()
