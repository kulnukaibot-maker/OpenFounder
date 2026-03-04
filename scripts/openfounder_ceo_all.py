#!/usr/bin/env python3
"""Run the CEO Loop for ALL active ventures.

Multi-venture support: iterates over every active venture, runs the CEO loop,
and produces a consolidated report. Designed to replace the single-venture cron.

Usage:
    python3 scripts/openfounder_ceo_all.py
    python3 scripts/openfounder_ceo_all.py --dry-run
    python3 scripts/openfounder_ceo_all.py --json
    python3 scripts/openfounder_ceo_all.py --venture MyStartup  # single venture (backwards compat)
"""

import argparse
import json
import logging
import sys
import os
import time

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from openfounder.state import list_ventures
from openfounder.ceo_loop import run_ceo_loop


def main():
    parser = argparse.ArgumentParser(
        prog="openfounder-ceo-all",
        description="Run the OpenFounder CEO Loop for all active ventures.",
    )
    parser.add_argument("--venture", "-v", help="Single venture name/ID (default: all active)")
    parser.add_argument("--dry-run", action="store_true", help="Call LLM but don't write to DB")
    parser.add_argument("--json", action="store_true", dest="json_output", help="Output raw JSON")
    parser.add_argument("--verbose", action="store_true", help="Enable debug logging")
    parser.add_argument("--continue-on-error", action="store_true",
                        help="Continue to next venture if one fails (default for multi)")

    args = parser.parse_args()

    level = logging.DEBUG if args.verbose else logging.INFO
    logging.basicConfig(
        level=level,
        format="%(asctime)s [%(name)s] %(levelname)s: %(message)s",
        datefmt="%H:%M:%S",
    )
    logger = logging.getLogger("openfounder.ceo")

    # Determine ventures to run
    if args.venture:
        venture_names = [args.venture]
    else:
        ventures = list_ventures()
        if not ventures:
            print("No active ventures found.", file=sys.stderr)
            sys.exit(1)
        venture_names = [v["name"] for v in ventures]
        # Always continue on error in multi-venture mode
        args.continue_on_error = True

    logger.info("Running CEO loop for %d venture(s): %s", len(venture_names), venture_names)

    results = []
    failed = []

    for name in venture_names:
        logger.info("=" * 60)
        logger.info("Starting: %s", name)
        start = time.time()

        try:
            result = run_ceo_loop(name, dry_run=args.dry_run)
            result["duration_s"] = round(time.time() - start, 1)
            results.append(result)
            logger.info("Completed: %s (%.1fs)", name, result["duration_s"])
        except Exception as e:
            duration = round(time.time() - start, 1)
            logger.error("Failed: %s after %.1fs — %s", name, duration, e)
            failed.append({"venture": name, "error": str(e), "duration_s": duration})
            if not args.continue_on_error:
                print(f"Fatal error for {name}: {e}", file=sys.stderr)
                sys.exit(1)

    # Output
    consolidated = {
        "ventures_run": len(results),
        "ventures_failed": len(failed),
        "total_decisions": sum(r["decisions_recorded"] for r in results),
        "total_approvals": sum(r["approvals_submitted"] for r in results),
        "total_delegations": sum(r["delegations_run"] for r in results),
        "results": results,
        "failures": failed,
    }

    if args.json_output:
        print(json.dumps(consolidated, indent=2, default=str))
    else:
        print(f"\n{'='*60}")
        print(f"  OpenFounder CEO Loop — Multi-Venture Report")
        if args.dry_run:
            print(f"  [DRY RUN — no database writes]")
        print(f"{'='*60}\n")

        for r in results:
            usage = r["ceo_output"].get("_usage", {})
            print(f"  {r['venture']} (Loop #{r['loop_number']}, {r['duration_s']}s)")
            print(f"    Decisions: {r['decisions_recorded']}  Approvals: {r['approvals_submitted']}  Delegations: {r['delegations_run']}")
            print(f"    Model: {usage.get('model', '?')}  Tokens: {usage.get('input_tokens', 0)} in / {usage.get('output_tokens', 0)} out")
            if r.get("errors"):
                print(f"    Errors: {r['errors']}")
            print()

        for f in failed:
            print(f"  FAILED: {f['venture']} — {f['error']} ({f['duration_s']}s)")

        print(f"{'─'*60}")
        print(f"  Total: {consolidated['ventures_run']} succeeded, {consolidated['ventures_failed']} failed")
        print(f"  Decisions: {consolidated['total_decisions']}  Approvals: {consolidated['total_approvals']}")
        print(f"{'='*60}\n")

    if failed:
        sys.exit(1)


if __name__ == "__main__":
    main()
