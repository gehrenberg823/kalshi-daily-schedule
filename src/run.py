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

    cfg = load_config()
    days_ahead = cfg["display"].get("days_ahead", 1)
    log.info("Building schedule for %s through %s", target, target + timedelta(days=days_ahead))

    events_with_dates = discover_events(target, cfg)
    log.info("Found %d events", len(events_with_dates))

    rows = build_schedule(events_with_dates, cfg, target_date=target)
    log.info("Schedule has %d rows", len(rows))

    # key = the join value stored on each row; label adds the weekday for the chip
    dates = [{"key": d.strftime("%b %-d"), "label": d.strftime("%a %b %-d")}
             for d in (target + timedelta(days=i) for i in range(days_ahead + 1))]
    out = render(rows, target.isoformat(), dates)
    log.info("Rendered to %s", out)


if __name__ == "__main__":
    main()
