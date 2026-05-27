"""Kalshi public-API client. Paginates the events endpoint to discover
all open sports events, then fetches individual market details when
needed for start-time extraction.
"""
from __future__ import annotations

import json
import logging
import time

import requests

from .config import load_config

log = logging.getLogger(__name__)


def _get(base: str, path: str, params: dict, ua: str, timeout: int) -> dict:
    backoff = 1.0
    for attempt in range(5):
        r = requests.get(
            f"{base}{path}", params=params, headers={"User-Agent": ua}, timeout=timeout
        )
        if r.status_code == 429:
            log.warning("Rate limited (attempt %d), backing off %.1fs", attempt + 1, backoff)
            time.sleep(backoff)
            backoff *= 2
            continue
        r.raise_for_status()
        return json.loads(r.text, strict=False)
    r.raise_for_status()
    return json.loads(r.text, strict=False)


def paginate_events(cfg: dict | None = None) -> list[dict]:
    """Return all open events from Kalshi, paginating through the full list."""
    cfg = cfg or load_config()
    base = cfg["kalshi"]["base_url"]
    ua = cfg["http"]["user_agent"]
    timeout = cfg["http"]["timeout_seconds"]
    sleep = cfg["http"].get("sleep_between_calls", 0.4)

    all_events: list[dict] = []
    cursor = None
    page = 0

    while True:
        params: dict = {"status": "open", "limit": 200}
        if cursor:
            params["cursor"] = cursor
        data = _get(base, "/events", params, ua, timeout)
        events = data.get("events", [])
        all_events.extend(events)
        cursor = data.get("cursor")
        page += 1
        log.info("Page %d: %d events (total %d)", page, len(events), len(all_events))
        if not cursor or not events:
            break
        time.sleep(sleep)

    return all_events


def fetch_first_market(event_ticker: str, cfg: dict | None = None) -> dict | None:
    """Fetch the first market for an event to extract rules_primary / close_time."""
    cfg = cfg or load_config()
    base = cfg["kalshi"]["base_url"]
    ua = cfg["http"]["user_agent"]
    timeout = cfg["http"]["timeout_seconds"]

    data = _get(base, "/markets", {"event_ticker": event_ticker, "limit": 1}, ua, timeout)
    markets = data.get("markets") or []
    return markets[0] if markets else None
