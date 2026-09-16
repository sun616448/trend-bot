"""Hacker News front page over the last week via the Algolia API."""
from __future__ import annotations

import time

from trendbot.collectors.base import clean, client, get_json, log, ts_to_dt
from trendbot.models import Signal


def collect() -> list[Signal]:
    since = int(time.time()) - 7 * 86400
    out: list[Signal] = []
    with client() as c:
        data = get_json(
            c,
            "https://hn.algolia.com/api/v1/search",
            params={"tags": "story", "numericFilters": f"created_at_i>{since},points>150", "hitsPerPage": 40},
        )
    for h in (data or {}).get("hits", []):
        url = h.get("url") or f"https://news.ycombinator.com/item?id={h['objectID']}"
        out.append(
            Signal(
                id=Signal.make_id("hackernews", url),
                source="hackernews",
                source_label="Hacker News",
                title=clean(h.get("title"), 200),
                url=url,
                text=clean(h.get("story_text") or ""),
                published=ts_to_dt(h.get("created_at_i")),
                score=float(h.get("points", 0)),
                metrics={"points": h.get("points", 0), "comments": h.get("num_comments", 0), "hn_url": f"https://news.ycombinator.com/item?id={h['objectID']}"},
            )
        )
    log.info("hackernews: %d", len(out))
    return out
