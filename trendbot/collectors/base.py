from __future__ import annotations

import html
import logging
import time
from datetime import datetime, timezone

import httpx

from trendbot.config import BROWSER_UA, USER_AGENT

log = logging.getLogger("trendbot")


def client(browser_like: bool = False, headers: dict | None = None, **kw) -> httpx.Client:
    ua = BROWSER_UA if browser_like else USER_AGENT
    h = {"User-Agent": ua, "Accept-Language": "en-US,en;q=0.9", **(headers or {})}
    return httpx.Client(headers=h, timeout=25, follow_redirects=True, **kw)


def get_json(c: httpx.Client, url: str, retries: int = 2, **kw):
    for attempt in range(retries + 1):
        try:
            r = c.get(url, **kw)
            if r.status_code in (429, 403) and attempt < retries:
                time.sleep(5 * (attempt + 1))
                continue
            r.raise_for_status()
            return r.json()
        except (httpx.HTTPError, ValueError) as e:
            if attempt >= retries:
                log.warning("GET %s failed: %s", url, e)
                return None
            time.sleep(1.5)
    return None


def ts_to_dt(ts: float | int | None) -> datetime | None:
    if not ts:
        return None
    return datetime.fromtimestamp(float(ts), tz=timezone.utc)


def clean(s: str | None, limit: int = 600) -> str:
    if not s:
        return ""
    s = " ".join(html.unescape(str(s)).split())
    return s[:limit]
