"""Trade and culture press via RSS. Only items from the last 8 days."""
from __future__ import annotations

import re
import time
from datetime import datetime, timedelta, timezone

import feedparser

from trendbot.collectors.base import clean, client, log
from trendbot.config import PER_FEED, RSS_FEEDS
from trendbot.models import Signal

TAG_RE = re.compile(r"<[^>]+>")


def _dt(e) -> datetime | None:
    t = e.get("published_parsed") or e.get("updated_parsed")
    if not t:
        return None
    return datetime(*t[:6], tzinfo=timezone.utc)


def _image(e) -> str | None:
    for m in e.get("media_content", []) or []:
        if m.get("url") and "image" in (m.get("type") or "image"):
            return m["url"]
    for m in e.get("media_thumbnail", []) or []:
        if m.get("url"):
            return m["url"]
    for l in e.get("links", []) or []:
        if l.get("rel") == "enclosure" and str(l.get("type", "")).startswith("image"):
            return l.get("href")
    html = e.get("summary", "") or ""
    m = re.search(r'<img[^>]+src="([^"]+)"', html)
    return m.group(1) if m else None


def collect() -> list[Signal]:
    cutoff = datetime.now(timezone.utc) - timedelta(days=8)
    out: list[Signal] = []
    with client(browser_like=True) as c:
        for label, url in RSS_FEEDS.items():
            try:
                r = c.get(url)
            except Exception as e:  # noqa: BLE001
                log.warning("rss %s: %s", label, e)
                continue
            if r.status_code != 200:
                log.warning("rss %s: HTTP %s", label, r.status_code)
                continue
            feed = feedparser.parse(r.text)
            n = 0
            for e in feed.entries:
                d = _dt(e)
                if d and d < cutoff:
                    continue
                link = e.get("link")
                if not link:
                    continue
                summary = TAG_RE.sub(" ", e.get("summary", "") or "")
                out.append(
                    Signal(
                        id=Signal.make_id("rss", link),
                        source="rss",
                        source_label=label,
                        title=clean(e.get("title"), 200),
                        url=link,
                        text=clean(summary, 400),
                        published=d,
                        rank=n + 1,
                        image_url=_image(e),
                    )
                )
                n += 1
                if n >= PER_FEED:
                    break
            time.sleep(0.2)
    log.info("rss: %d from %d feeds", len(out), len(RSS_FEEDS))
    return out
