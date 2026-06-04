#!/usr/bin/env python3
"""Lightweight viewer for Otedama performance snapshots.

Reads structured JSON log lines (output by `PerformanceMonitor`) and displays
key metric trends in a tabular, human-friendly format.
"""

from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime
from pathlib import Path
from typing import Any, Iterable, List, Sequence

DEFAULT_METRICS = (
    "memory.percent",
    "cpu.percent",
    "disk_io.write_kbps",
    "disk_io.read_kbps",
    "network_io.throughput_kbps",
    "process_memory.percent",
)


def parse_args(argv: Sequence[str]) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Display recent performance snapshots from Otedama logs.",
    )
    parser.add_argument(
        "--log-file",
        type=Path,
        default=Path("logs") / "otedama.log",
        help="Path to the JSON log file (default: logs/otedama.log)",
    )
    parser.add_argument(
        "--limit",
        type=int,
        default=20,
        help="Number of latest snapshots to display (default: 20)",
    )
    parser.add_argument(
        "--metrics",
        type=str,
        default=",".join(DEFAULT_METRICS),
        help=(
            "Comma-separated list of metrics to display. "
            "Use dotted paths, e.g. memory.percent,cpu.percent"
        ),
    )
    parser.add_argument(
        "--reverse",
        action="store_true",
        help="Show oldest snapshots first instead of newest first.",
    )
    return parser.parse_args(argv)


def iter_log_entries(path: Path) -> Iterable[dict[str, Any]]:
    if not path.exists():
        raise FileNotFoundError(f"Log file not found: {path}")

    with path.open("r", encoding="utf-8") as log_file:
        for line in log_file:
            line = line.strip()
            if not line:
                continue
            try:
                yield json.loads(line)
            except json.JSONDecodeError:
                continue


def collect_snapshots(path: Path) -> List[dict[str, Any]]:
    snapshots: List[dict[str, Any]] = []
    for entry in iter_log_entries(path):
        message = entry.get("message")
        extra = entry.get("extra") or {}
        if message != "performance_snapshot":
            continue
        stats = extra.get("stats") or {}
        timestamp = entry.get("timestamp") or stats.get("timestamp")
        snapshots.append({
            "timestamp": timestamp,
            "stats": stats,
        })
    return snapshots


def extract_metric(stats: dict[str, Any], path: str) -> Any:
    current: Any = stats
    for key in path.split('.'):
        if isinstance(current, dict) and key in current:
            current = current[key]
        else:
            return None
    return current


def format_value(value: Any) -> str:
    if value is None:
        return "-"
    if isinstance(value, (int, float)):
        if abs(value) >= 100:
            return f"{value:,.0f}"
        return f"{value:,.2f}"
    return str(value)


def main(argv: Sequence[str] | None = None) -> int:
    args = parse_args(argv or sys.argv[1:])

    try:
        snapshots = collect_snapshots(args.log_file)
    except FileNotFoundError as exc:
        print(exc, file=sys.stderr)
        return 1

    if not snapshots:
        print("No performance snapshots found.")
        return 0

    snapshots.sort(
        key=lambda item: item.get("timestamp") or "",
        reverse=not args.reverse,
    )

    metrics = [item.strip() for item in args.metrics.split(',') if item.strip()]
    header = ["timestamp", *metrics]

    rows: List[List[str]] = []
    for snapshot in snapshots[: args.limit]:
        timestamp = snapshot.get("timestamp") or ""
        try:
            ts_display = datetime.fromisoformat(timestamp).strftime("%Y-%m-%d %H:%M:%S")
        except ValueError:
            ts_display = timestamp

        stats = snapshot.get("stats", {})
        row = [ts_display]
        for metric in metrics:
            value = extract_metric(stats, metric)
            row.append(format_value(value))
        rows.append(row)

    column_widths = [max(len(str(item)) for item in column) for column in zip(header, *rows)]

    def render_line(values: Sequence[str]) -> str:
        return "  ".join(text.ljust(width) for text, width in zip(values, column_widths))

    print(render_line(header))
    print("  ".join("-" * width for width in column_widths))
    for row in rows:
        print(render_line(row))

    return 0


if __name__ == "__main__":
    sys.exit(main())
