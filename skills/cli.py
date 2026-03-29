# skills/cli.py
# Command-line interface for the Evolution Agent skills manager.
#
# Usage:
#   python -m skills add bitrefill/agents
#   python -m skills list
#   python -m skills remove <skill-id>
#   python -m skills info <skill-id>

import argparse
import json
import sys

from skills import registry


def _cmd_add(args: argparse.Namespace) -> int:
    skill_id = args.skill_id
    existing = registry.get_skill(skill_id)
    if existing:
        print(f"✓ Skill '{skill_id}' is already installed.")
        _print_skill(existing)
        return 0

    # For built-in skills (shipped with the repo) the entry already lives in
    # the registry; for external skills a stub entry is created so the operator
    # can fill in the module / class details.
    print(f"Skill '{skill_id}' is not a built-in skill.")
    print(
        "To add a custom skill, register it programmatically via "
        "skills.registry.register_skill(entry)."
    )
    return 1


def _cmd_list(args: argparse.Namespace) -> int:
    skills = registry.list_skills()
    if not skills:
        print("No skills installed.")
        return 0
    print(f"{'ID':<30} {'NAME':<35} {'BUILTIN'}")
    print("-" * 75)
    for s in skills:
        builtin = "yes" if s.get("builtin") else "no"
        print(f"{s.get('id', ''):<30} {s.get('name', ''):<35} {builtin}")
    return 0


def _cmd_info(args: argparse.Namespace) -> int:
    skill_id = args.skill_id
    entry = registry.get_skill(skill_id)
    if entry is None:
        print(f"Skill '{skill_id}' is not installed.", file=sys.stderr)
        return 1
    _print_skill(entry)
    return 0


def _cmd_remove(args: argparse.Namespace) -> int:
    skill_id = args.skill_id
    try:
        removed = registry.unregister_skill(skill_id)
    except ValueError as exc:
        print(f"Error: {exc}", file=sys.stderr)
        return 1
    if removed:
        print(f"Skill '{skill_id}' removed.")
        return 0
    print(f"Skill '{skill_id}' was not found.", file=sys.stderr)
    return 1


def _print_skill(entry: dict) -> None:
    print(json.dumps(entry, indent=2))


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="skills",
        description="Evolution Agent skills manager – add, list, and inspect agent skills.",
    )
    sub = parser.add_subparsers(dest="command", required=True)

    p_add = sub.add_parser("add", help="Install a skill.")
    p_add.add_argument("skill_id", metavar="SKILL_ID", help="e.g. bitrefill/agents")
    p_add.set_defaults(func=_cmd_add)

    p_list = sub.add_parser("list", help="List installed skills.")
    p_list.set_defaults(func=_cmd_list)

    p_info = sub.add_parser("info", help="Show details about a skill.")
    p_info.add_argument("skill_id", metavar="SKILL_ID")
    p_info.set_defaults(func=_cmd_info)

    p_remove = sub.add_parser("remove", help="Remove a custom skill.")
    p_remove.add_argument("skill_id", metavar="SKILL_ID")
    p_remove.set_defaults(func=_cmd_remove)

    return parser


def main(argv=None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    return args.func(args)


if __name__ == "__main__":
    sys.exit(main())
