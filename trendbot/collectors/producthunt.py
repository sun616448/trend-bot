"""Product Hunt public Atom feed (newest launches)."""
from __future__ import annotations

import re

import feedparser

from trendbot.collectors.base import clean, client, log
from trendbot.models import Signal


def collect() -> list[Signal]:
    out: list[Signal] = []
    with client(browser_like=True) as c:
        r = c.get("https://www.producthunt.com/feed")
        if r.status_code != 200:
            log.warning("producthunt feed %s", r.status_code)
            return out
    feed = feedparser.parse(r.text)
    for i, e in enumerate(feed.entries[:40], 1):
        out.append(
            Signal(
                id=Signal.make_id("producthunt", e.link),
                source="producthunt",
                source_label="Product Hunt",
                title=clean(e.get("title"), 160),
                url=e.link,
                text=clean(re.sub(r"<[^>]+>", " ", e.get("summary", "") or ""), 300),
                rank=i,
            )
        )
    log.info("producthunt: %d", len(out))
    return out
