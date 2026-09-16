"""YouTube most-popular videos (US). Optional: needs YOUTUBE_API_KEY (free Data API v3 key)."""
from __future__ import annotations

import os
from datetime import datetime

from trendbot.collectors.base import clean, client, get_json, log
from trendbot.models import Signal


def collect() -> list[Signal]:
    key = os.environ.get("YOUTUBE_API_KEY")
    if not key:
        log.info("youtube: skipped (no YOUTUBE_API_KEY)")
        return []
    out: list[Signal] = []
    with client() as c:
        data = get_json(
            c,
            "https://www.googleapis.com/youtube/v3/videos",
            params={"part": "snippet,statistics", "chart": "mostPopular", "regionCode": "US", "maxResults": 40, "key": key},
        )
    for i, v in enumerate((data or {}).get("items", []), 1):
        sn, st = v.get("snippet", {}), v.get("statistics", {})
        url = f"https://www.youtube.com/watch?v={v['id']}"
        out.append(
            Signal(
                id=Signal.make_id("youtube", url),
                source="youtube",
                source_label=f"YouTube · {sn.get('channelTitle', '')}",
                title=clean(sn.get("title"), 160),
                url=url,
                text=clean(sn.get("description"), 300),
                published=datetime.fromisoformat(sn["publishedAt"].replace("Z", "+00:00")) if sn.get("publishedAt") else None,
                score=float(st.get("viewCount", 0)),
                rank=i,
                metrics={"views": int(st.get("viewCount", 0)), "likes": int(st.get("likeCount", 0))},
                image_url=(sn.get("thumbnails", {}).get("high") or {}).get("url"),
            )
        )
    log.info("youtube: %d", len(out))
    return out
