# evolution/__main__.py
# Entrypoint: python -m evolution [project_root] [--interval N]
#
# Examples:
#   python -m evolution
#   python -m evolution /path/to/project --interval 60

import argparse
import os
from evolution.supervisor import Supervisor


def main():
    parser = argparse.ArgumentParser(
        prog="python -m evolution",
        description="Evolution Agent – self-evolving autonomous system supervisor.",
    )
    parser.add_argument(
        "project_root",
        nargs="?",
        default=os.getcwd(),
        help="Path to the project root directory (default: current directory).",
    )
    parser.add_argument(
        "--interval",
        type=int,
        default=30,
        metavar="SECONDS",
        help="Seconds to sleep between evolution cycles (default: 30).",
    )
    args = parser.parse_args()

    supervisor = Supervisor(args.project_root)
    supervisor.run(interval=args.interval)


if __name__ == "__main__":
    main()
