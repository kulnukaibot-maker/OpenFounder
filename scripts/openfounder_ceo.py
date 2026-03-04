#!/usr/bin/env python3
"""CLI entry point for the OpenFounder CEO Loop.

Usage:
    python3 scripts/openfounder_ceo.py --venture MyStartup
    python3 scripts/openfounder_ceo.py --venture MyStartup --dry-run
    python3 scripts/openfounder_ceo.py --venture MyStartup --json
"""

import argparse
import json
import logging
import sys
import os

# Add project root to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from openfounder.ceo_loop import run_ceo_loop


def main():
    parser = argparse.ArgumentParser(
        prog="openfounder-ceo",
        description="Run the OpenFounder CEO Loop for a venture.",
    )
    parser.add_argument("--venture", "-v", required=True, help="Venture name or ID")
    parser.add_argument("--dry-run", action="store_true", help="Call LLM but don't write to DB")
    parser.add_argument("--json", action="store_true", dest="json_output", help="Output raw JSON")
    parser.add_argument("--verbose", action="store_true", help="Enable debug logging")

    args = parser.parse_args()

    # Setup logging
    level = logging.DEBUG if args.verbose else logging.INFO
    logging.basicConfig(
        level=level,
        format="%(asctime)s [%(name)s] %(levelname)s: %(message)s",
        datefmt="%H:%M:%S",
    )

    try:
        result = run_ceo_loop(args.venture, dry_run=args.dry_run)
    except ValueError as e:
        print(f"Error: {e}", file=sys.stderr)
        sys.exit(1)
    except Exception as e:
        logging.getLogger("openfounder.ceo").exception("CEO loop failed")
        print(f"Fatal error: {e}", file=sys.stderr)
        sys.exit(1)

    if args.json_output:
        print(json.dumps(result, indent=2, default=str))
    else:
        # Human-readable output
        print(f"\n{'='*60}")
        print(f"  OpenFounder CEO Loop — {result['venture']}")
        print(f"  Loop #{result['loop_number']}")
        if result["dry_run"]:
            print(f"  [DRY RUN — no database writes]")
        print(f"{'='*60}\n")

        print(result["briefing"])

        print(f"\n{'─'*60}")
        print(f"  Decisions: {result['decisions_recorded']}")
        print(f"  Approvals: {result['approvals_submitted']}")
        print(f"  Metrics:   {result['metrics_recorded']}")

        # Show priorities
        priorities = result["ceo_output"].get("priorities", [])
        if priorities:
            print(f"\n  Priorities:")
            for p in priorities:
                print(f"    [{p.get('urgency', '?')}] {p['title']} → {p.get('assigned_crew', '?')}")

        # Show risks
        risks = result["ceo_output"].get("risks", [])
        if risks:
            print(f"\n  Risks:")
            for r in risks:
                print(f"    [{r.get('severity', '?')}] {r['title']}")

        # Show delegations
        delegations = result["ceo_output"].get("delegations", [])
        if delegations:
            print(f"\n  Delegations:")
            for d in delegations:
                print(f"    → {d['crew']}: {d['task']}")

        # Token usage
        usage = result["ceo_output"].get("_usage", {})
        if usage:
            print(f"\n{'─'*60}")
            print(f"  Model: {usage.get('model', '?')}")
            print(f"  Tokens: {usage.get('input_tokens', 0)} in / {usage.get('output_tokens', 0)} out")

        print(f"{'='*60}\n")


if __name__ == "__main__":
    main()
