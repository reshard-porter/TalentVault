"""Command-line entry point.

    python run.py                    # uses config.yaml
    python run.py --limit 5          # quick test on the first 5 candidates
    python run.py --fresh            # ignore any unfinished previous run
    python run.py --show-browser     # watch the browser work
"""
from __future__ import annotations

import argparse
import sys

from exporter.config import ConfigError, load_config
from exporter.runner import run_export
from exporter.sites import LoginError


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Export candidate contacts to Excel and resumes to PDF.")
    parser.add_argument("--config", default="config.yaml", help="path to the config file")
    parser.add_argument("--limit", type=int, help="process at most N candidates")
    parser.add_argument("--fresh", action="store_true", help="start over instead of resuming")
    parser.add_argument("--show-browser", action="store_true", help="run with a visible browser window")
    args = parser.parse_args(argv)

    try:
        cfg = load_config(args.config)
    except ConfigError as exc:
        print(f"Config problem: {exc}", file=sys.stderr)
        return 2
    if args.limit:
        cfg.max_records = args.limit
    if args.show_browser:
        cfg.headless = False

    try:
        result = run_export(cfg, fresh=args.fresh)
    except LoginError as exc:
        print(f"Login failed: {exc} Check the username and password.", file=sys.stderr)
        return 3
    except KeyboardInterrupt:
        print("\nStopped. Progress is saved; run the same command again to continue.", file=sys.stderr)
        return 130
    return 1 if result.failed else 0


if __name__ == "__main__":
    sys.exit(main())
