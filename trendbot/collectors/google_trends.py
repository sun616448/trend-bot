"""Google Trends daily trending searches (US) via the public RSS feed."""
from __future__ import annotations

import feedparser

from trendbot.collectors.base import clean, client, log
from trendbot.models import Signal


def _traffic(s: str) -> float:
    s = (s or "").replace("+", "").replace(",", "").strip().upper()
    mult = 1
    if s.endswith("K"):
        mult, s = 1_000, s[:-1]
    elif s.endswith("M"):
        mult, s = 1_000_000, s[:-1]
    try:
        return float(s) * mult
    except ValueError:
        return 0.0


def collect() -> list[Signal]:
    out: list[Signal] = []
    with client(browser_like=True) as c:
        r = c.get("https://trends.google.com/trending/rss?geo=US")
        if r.status_code != 200:
            log.warning("google trends rss %s", r.status_code)
            return out
    feed = feedparser.parse(r.text)
    for i, e in enumerate(feed.entries, 1):
        news = e.get("ht_news_item_url") or ""
        title = e.get("title", "")
        out.append(
            Signal(
                id=Signal.make_id("google_trends", title),
                source="google_trends",
                source_label="Google Trends (US)",
                title=clean(title, 120),
                url=f"https://trends.google.com/trends/explore?q={title.replace(' ', '+')}&geo=US&date=now%207-d",
                text=clean(f"{e.get('ht_news_item_title', '')} — {e.get('ht_news_item_snippet', '')} ({e.get('ht_news_item_source', '')}) {news}"),
                score=_traffic(e.get("ht_approx_traffic")),
                rank=i,
                metrics={"approx_searches": e.get("ht_approx_traffic", ""), "news_url": news},
                image_url=e.get("ht_picture"),
            )
        )
    log.info("google_trends: %d", len(out))
    return out
