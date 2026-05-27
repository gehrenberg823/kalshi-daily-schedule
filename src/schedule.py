"""Core logic: discover today's sports events, extract start times, build schedule."""
from __future__ import annotations

import logging
import re
import time
from datetime import date, datetime, time as dt_time, timezone, timedelta
from zoneinfo import ZoneInfo

from . import kalshi
from .config import load_config

log = logging.getLogger(__name__)

MONTH_MAP = {
    "JAN": 1, "FEB": 2, "MAR": 3, "APR": 4, "MAY": 5, "JUN": 6,
    "JUL": 7, "AUG": 8, "SEP": 9, "OCT": 10, "NOV": 11, "DEC": 12,
}

EDT = ZoneInfo("America/New_York")
CT = ZoneInfo("America/Chicago")

# Regex: after the first dash, look for YYMMMDD optionally followed by HHMM
_TICKER_DATE_RE = re.compile(r"-(\d{2})([A-Z]{3})(\d{2})")
_TICKER_TIME_RE = re.compile(r"-\d{2}[A-Z]{3}\d{2}(\d{4})")

# Regex for "at H:MM PM EDT" or "at HH:MM PM EDT" in rules_primary
_RULES_TIME_RE = re.compile(r"at (\d{1,2}):(\d{2})\s*(AM|PM)\s*(E[DS]T)", re.IGNORECASE)


def _parse_date_from_ticker(ticker: str) -> date | None:
    m = _TICKER_DATE_RE.search(ticker)
    if not m:
        return None
    yy, mon, dd = m.group(1), m.group(2), m.group(3)
    month = MONTH_MAP.get(mon.upper())
    if not month:
        return None
    try:
        return date(2000 + int(yy), month, int(dd))
    except ValueError:
        return None


def _parse_time_from_ticker(ticker: str) -> dt_time | None:
    """Extract HHMM (military, EDT) from ticker if present."""
    m = _TICKER_TIME_RE.search(ticker)
    if not m:
        return None
    hhmm = m.group(1)
    try:
        return dt_time(int(hhmm[:2]), int(hhmm[2:]))
    except ValueError:
        return None


def _parse_time_from_rules(rules: str) -> dt_time | None:
    """Extract start time from rules_primary text like 'at 8:05 PM EDT'."""
    m = _RULES_TIME_RE.search(rules)
    if not m:
        return None
    h, mi, ampm, _ = m.groups()
    h = int(h)
    mi = int(mi)
    if ampm.upper() == "PM" and h != 12:
        h += 12
    elif ampm.upper() == "AM" and h == 12:
        h = 0
    try:
        return dt_time(h, mi)
    except ValueError:
        return None


def _to_ct(d: date, t: dt_time) -> datetime:
    """Combine date + time (assumed EDT) and convert to Central Time."""
    edt_dt = datetime.combine(d, t, tzinfo=EDT)
    return edt_dt.astimezone(CT)


def extract_start_time(event: dict, market: dict | None = None) -> datetime | None:
    """Best-effort start time extraction, returned in Central Time."""
    ticker = event["event_ticker"]
    event_date = _parse_date_from_ticker(ticker)
    if not event_date:
        return None

    # 1. Try ticker-embedded HHMM (EDT military time)
    ticker_time = _parse_time_from_ticker(ticker)
    if ticker_time:
        return _to_ct(event_date, ticker_time)

    # 2. Try rules_primary from market
    if market and market.get("rules_primary"):
        rules_time = _parse_time_from_rules(market["rules_primary"])
        if rules_time:
            return _to_ct(event_date, rules_time)

    # 3. Try occurrence_datetime — for verified sports, Kalshi sets this
    #    exactly 3h after game start. For others (ITF, Challenger), it's
    #    a tournament-day bucket and unusable for individual match times.
    if market and market.get("occurrence_datetime"):
        competition = event.get("product_metadata", {}).get("competition", "")
        if OCCURRENCE_OFFSET_SPORTS is None or competition in OCCURRENCE_OFFSET_SPORTS:
            try:
                occ_dt = datetime.fromisoformat(market["occurrence_datetime"].replace("Z", "+00:00"))
                start_dt = occ_dt - OCCURRENCE_OFFSET
                start_ct = start_dt.astimezone(CT)
                if abs((start_ct.date() - event_date).days) <= 1:
                    return start_ct
            except (ValueError, TypeError):
                pass

    return None


OCCURRENCE_OFFSET = timedelta(hours=3)

# Sports where occurrence_datetime is set per-match (start + 3h).
# Use occurrence - 3h for all sports. This is exact for major sports and
# approximate for lower-level events (ITF, Challenger). Better than TBD.
OCCURRENCE_OFFSET_SPORTS = None  # None = apply to all sports


def _ct_date_for_event(event: dict) -> date | None:
    """Determine the Central Time date for an event.

    Events with a time in the ticker get converted from EDT → CT, which can
    shift the date (e.g. 00:15 EDT May 27 = 11:15 PM CT May 26).  Events
    without an embedded time fall back to the raw ticker date.
    """
    ticker = event["event_ticker"]
    ticker_date = _parse_date_from_ticker(ticker)
    if ticker_date is None:
        return None
    ticker_time = _parse_time_from_ticker(ticker)
    if ticker_time:
        ct_dt = _to_ct(ticker_date, ticker_time)
        return ct_dt.date()
    return ticker_date


def discover_events(target_date: date, cfg: dict | None = None) -> list[tuple[dict, date]]:
    """Paginate all Kalshi events, return Sports events for today + tomorrow
    (plus unsettled carryovers). Each item is (event_dict, ct_date)."""
    cfg = cfg or load_config()
    scope_filter = set(cfg["display"].get("scope_filter", ["Game"]))
    exclude_keywords = cfg["display"].get("exclude_competition_keywords", [])
    lookback_days = cfg["display"].get("lookback_days", 2)
    earliest = target_date - timedelta(days=lookback_days)
    latest = target_date + timedelta(days=1)

    all_events = kalshi.paginate_events(cfg)
    log.info("Total open events: %d", len(all_events))

    matched = []
    for e in all_events:
        if e.get("category") != "Sports":
            continue
        pm = e.get("product_metadata", {})
        competition = pm.get("competition", "")
        if any(kw.lower() in competition.lower() for kw in exclude_keywords):
            continue
        scope = pm.get("competition_scope", "")
        if scope_filter and scope not in scope_filter:
            continue
        ct_d = _ct_date_for_event(e)
        if ct_d is None:
            continue
        if ct_d > latest or ct_d < earliest:
            continue
        matched.append((e, ct_d))

    log.info("Sports events (scope=%s, %s to %s): %d", scope_filter, earliest, latest, len(matched))
    return matched


def _event_url(event: dict, template: str) -> str:
    ticker = event["event_ticker"]
    series = event.get("series_ticker", "")
    return template.format(
        series_lower=series.lower(),
        event_ticker_lower=ticker.lower(),
    )


def _league_label(event: dict, labels: dict) -> str:
    competition = event.get("product_metadata", {}).get("competition", "")
    return labels.get(competition, competition)


def build_schedule(events_with_dates: list[tuple[dict, date]], cfg: dict | None = None, target_date: date | None = None) -> list[dict]:
    """Build the final schedule: fetch start times where needed, sort, number."""
    cfg = cfg or load_config()
    target_date = target_date or date.today()
    url_template = cfg["kalshi"]["event_url_template"]
    labels = cfg["display"].get("competition_labels", {})
    sleep = cfg["http"].get("sleep_between_calls", 0.4)

    rows = []
    needs_market_fetch = []

    for e, ct_d in events_with_dates:
        ticker_time = _parse_time_from_ticker(e["event_ticker"])
        if ticker_time:
            event_date = _parse_date_from_ticker(e["event_ticker"])
            start_ct = _to_ct(event_date, ticker_time) if event_date else None
            rows.append(_make_row(e, start_ct, ct_d, url_template, labels, target_date))
        else:
            needs_market_fetch.append((e, ct_d))

    # Batch-fetch markets for events without ticker-embedded times
    if needs_market_fetch:
        log.info("Fetching market details for %d events without ticker times", len(needs_market_fetch))
        for e, ct_d in needs_market_fetch:
            market = kalshi.fetch_first_market(e["event_ticker"], cfg)
            start_ct = extract_start_time(e, market)
            rows.append(_make_row(e, start_ct, ct_d, url_template, labels, target_date))
            time.sleep(sleep)

    # Sort by start time (TBD events go to the end)
    rows.sort(key=lambda r: r["sort_key"])

    # Assign sequential numbers
    for i, row in enumerate(rows, 1):
        row["num"] = i

    return rows


THUNDERPICK_GAMES = {
    "League of Legends",
    "Valorant",
    "CS2",
    "Dota 2",
}


def _thunderpick_url(event: dict) -> str | None:
    competition = event.get("product_metadata", {}).get("competition", "")
    if competition not in THUNDERPICK_GAMES:
        return None
    title = event.get("title", "")
    if not title:
        return None
    from urllib.parse import quote_plus
    query = quote_plus(f"site:thunderpick.io {title}")
    return f"https://www.google.com/search?q={query}"


def _make_row(event: dict, start_ct: datetime | None, ct_d: date, url_template: str, labels: dict, min_date: date | None = None) -> dict:
    ct_str = start_ct.strftime("%-I:%M %p CT") if start_ct else "TBD"
    sort_ts = start_ct.timestamp() if start_ct else float("inf")
    display_date = ct_d if (min_date is None or ct_d >= min_date) else min_date
    date_label = display_date.strftime("%b %-d")
    return {
        "num": 0,
        "event": event.get("title", ""),
        "sub_title": event.get("sub_title", ""),
        "league": _league_label(event, labels),
        "date": date_label,
        "start_time": ct_str,
        "sort_key": sort_ts,
        "event_ticker": event["event_ticker"],
        "event_url": _event_url(event, url_template),
        "thunderpick_url": _thunderpick_url(event) or "",
    }
