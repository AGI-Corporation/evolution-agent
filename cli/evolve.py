#!/usr/bin/env python3
# cli/evolve.py
# CLI entry point for the Evolution Agent.
#
# Usage:
#   python -m cli.evolve --task "Optimize loop latency in engine.py" --pop_size 8
#   python -m cli.evolve --cycles 3 --interval 10
#
# Environment:
#   OPENAI_API_KEY  — required for LLM-powered agents

import argparse
import json
import os
import sys


def queue_task(project_root: str, task: str, pop_size: int) -> None:
    """
    Enqueue a natural-language task as a feature request in feature_queue.json.
    pop_size variants are added, each tagged with their index so the Planner
    can explore alternative implementations.
    """
    queue_path = os.path.join(project_root, "evolution", "feature_queue.json")
    os.makedirs(os.path.dirname(queue_path), exist_ok=True)

    try:
        with open(queue_path, "r") as f:
            queue = json.load(f)
    except (FileNotFoundError, json.JSONDecodeError):
        queue = []

    for i in range(pop_size):
        entry = {
            "name": task,
            "description": task,
            "variant": i + 1,
            "pop_size": pop_size,
        }
        queue.append(entry)

    with open(queue_path, "w") as f:
        json.dump(queue, f, indent=4)

    print(f"[cli.evolve] Enqueued {pop_size} variant(s) for task: '{task}'")
    print(f"[cli.evolve] Queue path: {queue_path}")


def main():
    parser = argparse.ArgumentParser(
        description=(
            "Evolution Agent CLI — queue tasks and run the autonomous evolution loop.\n\n"
            "Examples:\n"
            "  python -m cli.evolve --task 'Add retry logic to engine.py'\n"
            "  python -m cli.evolve --task 'Optimise loop latency' --pop_size 4 --cycles 2\n"
        ),
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument(
        "--task",
        type=str,
        default=None,
        help="Natural-language description of the task to evolve.",
    )
    parser.add_argument(
        "--pop_size",
        type=int,
        default=1,
        help="Number of population variants to enqueue for the task (default: 1).",
    )
    parser.add_argument(
        "--cycles",
        type=int,
        default=None,
        help="Maximum number of evolution cycles to run (default: run forever).",
    )
    parser.add_argument(
        "--interval",
        type=int,
        default=30,
        help="Seconds between evolution cycles (default: 30).",
    )
    parser.add_argument(
        "project_root",
        nargs="?",
        default=os.getcwd(),
        help="Path to the project root (default: current directory).",
    )
    args = parser.parse_args()

    project_root = os.path.abspath(args.project_root)

    if not os.getenv("OPENAI_API_KEY"):
        print("[cli.evolve] WARNING: OPENAI_API_KEY is not set. Agents will run in simulation mode.")

    # Enqueue the task before starting the supervisor
    if args.task:
        queue_task(project_root, args.task, args.pop_size)

    from evolution.supervisor import Supervisor

    supervisor = Supervisor(project_root)

    if args.cycles is not None:
        # Run a fixed number of cycles then exit
        for cycle in range(args.cycles):
            print(f"\n[cli.evolve] Cycle {cycle + 1}/{args.cycles}")
            supervisor.run_single_cycle()
            if cycle < args.cycles - 1:
                import time
                time.sleep(args.interval)
        summary = supervisor.reporter.generate_system_summary()
        print(f"\n[cli.evolve] Final system summary:")
        print(json.dumps(summary, indent=2))
    else:
        supervisor.run(interval=args.interval)


if __name__ == "__main__":
    main()
