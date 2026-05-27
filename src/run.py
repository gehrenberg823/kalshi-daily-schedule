"""Entrypoint: fetch Kalshi sports events and render the schedule."""
from __future__ import annotations

import argparse
import logging
from datetime import date, timedelta

from .config import load_config
from .schedule import discover_events, build_schedule
from .render import render

log = logging.getLogger(__name__)


def main():
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(levelname)s %(name)s: %(message)s",
        datefmt="%H:%M:%S",
    )

    parser = argparse.ArgumentParser(description="Kalshi Daily Sports Schedule")
    parser.add_argument("--date", help="Target date (YYYY-MM-DD), default today")
    args = parser.parse_args()

    if args.date:
        target = date.fromisoformat(args.date)
    else:
        target = date.today()

    tomorrow = target + timedelta(days=1)
    log.info("Building schedule for %s and %s", target, tomorrow)
    cfg = load_config()

    events_with_dates = discover_events(target, cfg)
    log.info("Found %d events", len(events_with_dates))

    rows = build_schedule(events_with_dates, cfg, target_date=target)
    log.info("Schedule has %d rows", len(rows))

    dates = [target.strftime("%b %-d"), tomorrow.strftime("%b %-d")]
    out = render(rows, target.isoformat(), dates)
    log.info("Rendered to %s", out)


if __name__ == "__main__":
    main()
