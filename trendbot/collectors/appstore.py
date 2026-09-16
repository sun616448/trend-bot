"""Apple App Store top free apps (US) via Apple's public marketing RSS."""
from __future__ import annotations

from trendbot.collectors.base import clean, client, get_json, log
from trendbot.models import Signal


def collect() -> list[Signal]:
    out: list[Signal] = []
    with client() as c:
        data = get_json(c, "https://rss.marketingtools.apple.com/api/v2/us/apps/top-free/25/apps.json")
    for a in (data or {}).get("feed", {}).get("results", []):
        rank = len(out) + 1
        out.append(
            Signal(
                id=Signal.make_id("appstore", a["url"]),
                source="appstore",
                source_label="App Store top free (US)",
                title=clean(f"#{rank} {a['name']}", 120),
                url=a["url"],
                text=clean(f"by {a.get('artistName', '')}. Genres: {', '.join(g['name'] for g in a.get('genres', []))}"),
                rank=rank,
                score=float(26 - rank),
                image_url=a.get("artworkUrl100"),
            )
        )
    log.info("appstore: %d", len(out))
    return out
