#!/usr/bin/env python3
"""Safely set the active Hermes Kanban implementation lanes."""

from __future__ import annotations

import argparse
import json
import subprocess
import sys

REVIEWER = "reviewer-sol"
IMPLEMENTATION_PROFILES = {
    "worker-flash-1",
    "worker-flash-2",
    "worker-flash-3",
    "worker-luna-1",
    "worker-luna-2",
    "worker-terra-1",
    "worker-glm-full",
    "worker-sol",
    "worker-astra",
}
DEFAULT_LIMIT = 5


def run(*args: str) -> str:
    completed = subprocess.run(
        ["hermes", *args],
        check=True,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
    )
    return completed.stdout.strip()


def running_implementation_profiles() -> set[str]:
    rows = json.loads(run("kanban", "list", "--status", "running", "--json") or "[]")
    return {
        str(row.get("assignee"))
        for row in rows
        if row.get("assignee") in IMPLEMENTATION_PROFILES
    }


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Set up to five active implementation profiles plus reviewer-sol."
    )
    parser.add_argument("profiles", nargs="+", help="Implementation profile names")
    parser.add_argument("--limit", type=int, default=DEFAULT_LIMIT)
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()

    profiles = list(dict.fromkeys(args.profiles))
    unknown = sorted(set(profiles) - IMPLEMENTATION_PROFILES)
    if unknown:
        parser.error("unknown implementation profile(s): " + ", ".join(unknown))
    if args.limit < 1:
        parser.error("--limit must be at least 1")
    if len(profiles) > args.limit:
        parser.error(f"requested {len(profiles)} implementation profiles; limit is {args.limit}")

    running = running_implementation_profiles()
    removed_running = sorted(running - set(profiles))
    if removed_running:
        parser.error(
            "refusing to remove running implementation profile(s): "
            + ", ".join(removed_running)
        )

    dispatch_profiles = [*profiles, REVIEWER]
    if args.dry_run:
        print(json.dumps({"dispatch_profiles": dispatch_profiles, "running": sorted(running)}))
        return 0

    run("config", "set", "kanban.dispatch_profiles", json.dumps(dispatch_profiles))
    observed = json.loads(run("config", "get", "kanban.dispatch_profiles", "--json"))
    if observed != dispatch_profiles:
        print(
            json.dumps({"error": "read-back mismatch", "expected": dispatch_profiles, "observed": observed}),
            file=sys.stderr,
        )
        return 1
    print(json.dumps({"dispatch_profiles": observed, "running": sorted(running)}))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
