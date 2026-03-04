#!/usr/bin/env python3
"""Launch the OpenFounder Mission Control dashboard.

Usage:
    python3 scripts/openfounder_dashboard.py
    python3 scripts/openfounder_dashboard.py --port 8080
    python3 scripts/openfounder_dashboard.py --host 0.0.0.0 --port 8080
"""

import argparse
import logging
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))


def main():
    parser = argparse.ArgumentParser(
        prog="openfounder-dashboard",
        description="Launch the OpenFounder Mission Control dashboard.",
    )
    parser.add_argument("--host", default="0.0.0.0", help="Bind host (default: 0.0.0.0)")
    parser.add_argument("--port", "-p", type=int, default=8111, help="Port (default: 8111)")
    parser.add_argument("--reload", action="store_true", help="Auto-reload on code changes (dev mode)")
    parser.add_argument("--verbose", action="store_true", help="Enable debug logging")

    args = parser.parse_args()

    level = logging.DEBUG if args.verbose else logging.INFO
    logging.basicConfig(
        level=level,
        format="%(asctime)s [%(name)s] %(levelname)s: %(message)s",
        datefmt="%H:%M:%S",
    )

    import uvicorn
    uvicorn.run(
        "openfounder.dashboard.app:app",
        host=args.host,
        port=args.port,
        reload=args.reload,
        log_level="debug" if args.verbose else "info",
    )


if __name__ == "__main__":
    main()
