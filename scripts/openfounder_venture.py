#!/usr/bin/env python3
"""Venture management CLI — wrapper around state.py for common operations.

Usage:
    python3 scripts/openfounder_venture.py create "MyStartup" -d "Description" -g "Goal"
    python3 scripts/openfounder_venture.py info MyStartup
    python3 scripts/openfounder_venture.py seed MyStartup
    python3 scripts/openfounder_venture.py list
"""

import argparse
import json
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from openfounder.state import (
    create_venture,
    get_state,
    get_venture,
    list_ventures,
    add_feature,
    add_metric,
    add_decision,
)


def _print(data):
    print(json.dumps(data, indent=2, default=str))


def cmd_create(args):
    v = create_venture(args.name, args.description, args.goal, args.stage)
    print(f"Venture created: {v['name']} (ID: {v['id']})")
    _print(v)


def cmd_info(args):
    state = get_state(args.venture)
    v = state["venture"]
    print(f"\n{'='*50}")
    print(f"  {v['name']} [{v['stage']}] — {v['status']}")
    print(f"{'='*50}")
    if v.get("description"):
        print(f"  {v['description']}")
    if v.get("goal"):
        print(f"  Goal: {v['goal']}")
    print(f"\n  Features:  {len(state['features'])}")
    print(f"  Bugs:      {len(state['bugs'])}")
    print(f"  Decisions: {len(state['recent_decisions'])} (last 7 days)")
    print(f"  Metrics:   {len(state['metrics'])}")
    print(f"  Campaigns: {len(state['campaigns'])}")
    print(f"  Pending:   {len(state['pending_approvals'])}")
    print(f"{'='*50}\n")

    if args.json:
        _print(state)


def cmd_list(args):
    ventures = list_ventures()
    if not ventures:
        print("No active ventures.")
        return
    for v in ventures:
        print(f"  [{v['id']}] {v['name']} — {v['stage']} ({v['status']})")


def cmd_seed(args):
    """Seed a venture with initial OpenFounder data."""
    v = get_venture(args.venture)
    if not v:
        print(f"Venture not found: {args.venture}", file=sys.stderr)
        sys.exit(1)

    name = v["name"]
    print(f"Seeding {name} with initial data...")

    # Features
    features = [
        ("CEO Loop (nightly)", "Nightly CEO loop reads state, makes decisions, delegates", "critical"),
        ("State Manager CLI", "Postgres CRUD with CLI interface for all entities", "critical"),
        ("Discord Approval Flow", "Send approval requests to Discord, process responses", "high"),
        ("Crew Execution", "Engineering, marketing, research crews with LLM calls", "high"),
        ("Decision Log Viewer", "CLI to review decisions with filtering", "medium"),
        ("Morning Briefing", "Human-readable summary sent to Discord", "high"),
    ]
    for title, desc, priority in features:
        add_feature(name, title, desc, priority)
        print(f"  + Feature: {title}")

    # Metrics
    metrics = [
        ("github_stars", 0, "count", "github"),
        ("lines_of_code", 0, "count", "cloc"),
        ("test_count", 0, "count", "pytest"),
        ("ceo_loops_run", 0, "count", "system"),
    ]
    for mname, val, unit, source in metrics:
        add_metric(name, mname, val, unit, source)
        print(f"  + Metric: {mname}")

    # Initial decision
    add_decision(
        name, "strategic",
        "Bootstrap OpenFounder as first venture",
        "Meta approach: the AI co-founder manages its own development. "
        "Proves the concept while building the product.",
        outcome="OpenFounder is both the product and the first customer",
        confidence=0.9,
        source="human",
    )
    print(f"  + Decision: Bootstrap strategy")

    print(f"\nSeeding complete. Run: python3 scripts/openfounder_venture.py info {name}")


def main():
    parser = argparse.ArgumentParser(
        prog="openfounder-venture",
        description="Manage OpenFounder ventures.",
    )
    sub = parser.add_subparsers(dest="command", required=True)

    # create
    p = sub.add_parser("create", help="Create a new venture")
    p.add_argument("name")
    p.add_argument("--description", "-d")
    p.add_argument("--goal", "-g")
    p.add_argument("--stage", default="idea", choices=["idea", "mvp", "growth", "scale"])

    # info
    p = sub.add_parser("info", help="Show venture info and stats")
    p.add_argument("venture")
    p.add_argument("--json", action="store_true", help="Also output full JSON state")

    # list
    sub.add_parser("list", help="List all active ventures")

    # seed
    p = sub.add_parser("seed", help="Seed a venture with initial OpenFounder data")
    p.add_argument("venture")

    args = parser.parse_args()

    commands = {
        "create": cmd_create,
        "info": cmd_info,
        "list": cmd_list,
        "seed": cmd_seed,
    }
    commands[args.command](args)


if __name__ == "__main__":
    main()
