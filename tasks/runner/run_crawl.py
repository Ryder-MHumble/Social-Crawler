#!/usr/bin/env python3
from __future__ import annotations

import argparse
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[2]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from tasks.common.engine import TaskExecutionEngine
from tasks.runner.registry import load_task_specs, resolve_task


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Unified crawler launcher for all task types.",
    )
    parser.add_argument(
        "task",
        nargs="?",
        help="Task slug or alias, e.g. sentiment_monitor / creator_outreach / vibe_coding",
    )
    parser.add_argument(
        "--list",
        action="store_true",
        help="Print all available tasks and exit.",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Print resolved jobs and commands without executing.",
    )
    return parser.parse_args()


def print_system_banner(task_specs) -> None:
    print("=" * 96)
    print("Social Crawler Task Center")
    print("=" * 96)
    print("Supported abilities:")
    for idx, spec in enumerate(task_specs, start=1):
        aliases = ", ".join(spec.aliases) if spec.aliases else "-"
        print(f"  {idx}. {spec.slug:18} {spec.short_desc}")
        print(f"     aliases: {aliases}")
    print("=" * 96)


def choose_task_interactively(task_specs):
    print_system_banner(task_specs)
    print("Select a task by number:")
    for idx, spec in enumerate(task_specs, start=1):
        print(f"  {idx}. {spec.title}")
    print("  0. Exit")

    while True:
        raw = input("Your choice: ").strip()
        if raw == "0":
            return None
        if raw.isdigit():
            value = int(raw)
            if 1 <= value <= len(task_specs):
                return task_specs[value - 1]
        print("Invalid selection. Please enter a valid number.")


def main() -> int:
    args = parse_args()
    task_specs = load_task_specs(PROJECT_ROOT, sys.executable)

    if args.list:
        print_system_banner(task_specs)
        return 0

    selected_task = None
    if args.task:
        selected_task = resolve_task(task_specs, args.task)
        if not selected_task:
            print(f"Unknown task: {args.task}")
            print("Use '--list' to view supported tasks.")
            return 1
    else:
        if not sys.stdin.isatty():
            print("No task provided in non-interactive mode.")
            print("Use '--list' or pass one task name, for example: run_crawl.sh sentiment_monitor")
            return 1
        selected_task = choose_task_interactively(task_specs)
        if not selected_task:
            print("Exit without running tasks.")
            return 0

    if args.dry_run:
        print("=" * 96)
        print(f"[Dry Run] {selected_task.title} ({selected_task.slug})")
        print("=" * 96)
        for idx, stage in enumerate(selected_task.stages, start=1):
            mode = "parallel" if stage.concurrent else "sequential"
            print(f"[Stage {idx}] {stage.name} | mode={mode} | jobs={len(stage.jobs)}")
            for job in stage.jobs:
                print(f"  - {job.name}")
                print(f"    cwd: {job.cwd}")
                print(f"    cmd: {' '.join(job.command)}")
        print("=" * 96)
        return 0

    engine = TaskExecutionEngine(PROJECT_ROOT)
    return engine.run_task(selected_task)


if __name__ == "__main__":
    try:
        sys.exit(main())
    except KeyboardInterrupt:
        print("\nInterrupted by user.")
        sys.exit(130)
