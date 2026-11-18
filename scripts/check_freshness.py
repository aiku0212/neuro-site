#!/usr/bin/env python3
"""Fail when status.json's last_run is older than allowed.

Usage: check_freshness.py [path/to/status.json] [--max-age-days N]

The daily workflow runs this with --max-age-days 0 against the status.json it just
pushed, so a run that did not save its heartbeat fails. The unit tests run it with the
default limit, so a schedule that has silently stopped shows up as a failing test.
"""
import argparse
import datetime
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
MAX_STATUS_AGE_DAYS = 3


def age_days(status, today):
    """Days since status["last_run"]; None if it is missing or unreadable."""
    try:
        return (today - datetime.date.fromisoformat(status["last_run"])).days
    except (KeyError, TypeError, ValueError):
        return None


def problem(status, today, max_age_days=MAX_STATUS_AGE_DAYS):
    """A message if the heartbeat is stale or missing, else None."""
    age = age_days(status, today)
    if age is None:
        return "status.json has no readable last_run date."
    if age > max_age_days:
        return (f"status.json last_run is {status['last_run']}, {age} days ago (limit {max_age_days}). "
                "The daily citation check has not saved a run since then.")
    return None


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("path", nargs="?", type=Path, default=ROOT / "data" / "status.json")
    parser.add_argument("--max-age-days", type=int, default=MAX_STATUS_AGE_DAYS)
    args = parser.parse_args(argv)
    try:
        status = json.loads(args.path.read_text(encoding="utf8"))
    except (OSError, ValueError) as err:
        status = {}
        print(f"Could not read {args.path}: {err}", file=sys.stderr)
    message = problem(status, datetime.datetime.now(datetime.timezone.utc).date(), args.max_age_days)
    if message:
        print(f"::error::{message}", file=sys.stderr)
        return 1
    print(f"Heartbeat is fresh: last_run {status['last_run']}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
