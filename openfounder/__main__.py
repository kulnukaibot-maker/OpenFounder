"""OpenFounder CLI entry point.

Usage:
    python -m openfounder              — Show help
    python -m openfounder setup        — Run database migrations
    python -m openfounder ceo          — Run CEO loop for all active ventures
    python -m openfounder dashboard    — Start the Mission Control dashboard
    python -m openfounder venture ...  — Venture management commands
"""

import subprocess
import sys
from pathlib import Path

SCRIPTS_DIR = Path(__file__).resolve().parent.parent / "scripts"


def main():
    if len(sys.argv) < 2:
        print(__doc__.strip())
        from openfounder import __version__
        print(f"\nVersion: {__version__}")
        sys.exit(0)

    cmd = sys.argv[1]
    rest = sys.argv[2:]

    scripts = {
        "setup": "openfounder_setup.py",
        "ceo": "openfounder_ceo_all.py",
        "dashboard": "openfounder_dashboard.py",
        "venture": "openfounder_venture.py",
    }

    if cmd not in scripts:
        print(f"Unknown command: {cmd}")
        print(__doc__.strip())
        sys.exit(1)

    script = SCRIPTS_DIR / scripts[cmd]
    if not script.exists():
        print(f"Script not found: {script}")
        sys.exit(1)

    sys.exit(subprocess.call([sys.executable, str(script)] + rest))


if __name__ == "__main__":
    main()
