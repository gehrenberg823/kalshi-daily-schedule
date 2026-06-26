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
    # Retry on rate limits (429), transient server errors (5xx), AND network
    # errors (connection reset/timeout). The Kalshi public API intermittently
    # resets connections mid-pagination; without retrying those, a single blip
    # aborts the whole daily run and the schedule silently goes stale.
    # The Kalshi public API rate-limits hard during the early-morning spike
    # (the 6 AM cron repeatedly died on sustained 429s). Use a generous attempt
    # budget with capped exponential backoff, and honor a Retry-After header
    # when the server tells us how long to wait.
    backoff = 1.0
    max_backoff = 60.0
    attempts = 8
    for attempt in range(attempts):
        try:
            r = requests.get(
                f"{base}{path}", params=params, headers={"User-Agent": ua}, timeout=timeout
            )
        except requests.exceptions.RequestException as exc:
            if attempt == attempts - 1:
                raise
            log.warning(
                "Network error on %s (attempt %d/%d): %s; retrying in %.1fs",
                path, attempt + 1, attempts, exc, backoff,
            )
            time.sleep(backoff)
            backoff = min(backoff * 2, max_backoff)
            continue
        if r.status_code == 429 or r.status_code >= 500:
            if attempt == attempts - 1:
                r.raise_for_status()
            wait = backoff
            retry_after = r.headers.get("Retry-After")
            if retry_after:
                try:
                    wait = max(wait, float(retry_after))
                except ValueError:
                    pass
            log.warning(
                "HTTP %d on %s (attempt %d/%d), backing off %.1fs",
                r.status_code, path, attempt + 1, attempts, wait,
            )
            time.sleep(wait)
            backoff = min(backoff * 2, max_backoff)
            continue
        r.raise_for_status()
        return json.loads(r.text, strict=False)
    raise RuntimeError(f"GET {path} failed after {attempts} attempts")


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
