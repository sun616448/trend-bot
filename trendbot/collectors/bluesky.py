"""Bluesky public search. No auth needed on api.bsky.app."""
from __future__ import annotations

import time
from datetime import datetime, timedelta, timezone

from trendbot.collectors.base import clean, client, get_json, log
from trendbot.config import BLUESKY_QUERIES
from trendbot.models import Signal


def collect() -> list[Signal]:
    out: dict[str, Signal] = {}
    since = (datetime.now(timezone.utc) - timedelta(days=7)).strftime("%Y-%m-%dT%H:%M:%SZ")
    with client() as c:
        for q in BLUESKY_QUERIES:
            data = get_json(
                c,
                "https://api.bsky.app/xrpc/app.bsky.feed.searchPosts",
                params={"q": q, "sort": "top", "limit": 25, "lang": "en", "since": since},
            )
            if not data:
                continue
            for p in data.get("posts", []):
                rec = p.get("record", {})
                likes = p.get("likeCount", 0)
                reposts = p.get("repostCount", 0)
                if likes + reposts < 20:
                    continue
                if any(l.get("val") in ("porn", "sexual", "nudity", "graphic-media") for l in p.get("labels", []) or []):
                    continue
                handle = p.get("author", {}).get("handle", "")
                rkey = p["uri"].rsplit("/", 1)[-1]
                url = f"https://bsky.app/profile/{handle}/post/{rkey}"
                img = None
                emb = p.get("embed", {})
                if emb.get("images"):
                    img = emb["images"][0].get("thumb")
                elif emb.get("external", {}).get("thumb"):
                    img = emb["external"]["thumb"]
                text = clean(rec.get("text"), 400)
                out[url] = Signal(
                    id=Signal.make_id("bluesky", url),
                    source="bluesky",
                    source_label=f"@{handle}",
                    title=text[:120],
                    url=url,
                    text=text,
                    published=datetime.fromisoformat(rec["createdAt"].replace("Z", "+00:00")) if rec.get("createdAt") else None,
                    score=float(likes + 2 * reposts),
                    metrics={"likes": likes, "reposts": reposts, "replies": p.get("replyCount", 0), "query": q},
                    image_url=img,
                )
            time.sleep(1.5)  # the search endpoint rate-limits bursts with 403s
    log.info("bluesky: %d signals", len(out))
    return list(out.values())
