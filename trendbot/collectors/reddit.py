"""Reddit, via the companion Devvit app in devvit/.

Reddit closed self-serve API keys in 2026 and blocks anonymous JSON/RSS from cloud networks,
so a Devvit app running inside Reddit exports the week's top posts to data/reddit/<week>.json
in this repo (see devvit/README.md). This collector just reads that file. If this week's file
is missing it falls back to the most recent one and says so.
"""
from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path

from trendbot.collectors.base import clean, log
from trendbot.models import Signal

REDDIT_DIR = Path(__file__).resolve().parent.parent.parent / "data" / "reddit"


def _week_now() -> str:
    y, w, _ = datetime.now(timezone.utc).isocalendar()
    return f"{y}-W{w:02d}"


def _pick_file() -> tuple[Path | None, str | None]:
    files = sorted(REDDIT_DIR.glob("*.json"))
    if not files:
        return None, None
    wanted = REDDIT_DIR / f"{_week_now()}.json"
    if wanted.exists():
        return wanted, None
    return files[-1], f"reddit: no export for {_week_now()}, using {files[-1].stem}"


def collect() -> list[Signal]:
    path, note = _pick_file()
    if path is None:
        log.warning("reddit: no export found in data/reddit/. Install the Devvit app (devvit/README.md).")
        return []
    if note:
        log.warning(note)
    data = json.loads(path.read_text())
    out: list[Signal] = []
    seen: set[str] = set()
    for p in data.get("posts", []):
        url = p.get("permalink") or ""
        if not url or url in seen:   # r/all and r/popular repeat posts from the other subs
            continue
        seen.add(url)
        text = clean(p.get("body"))
        if not text and p.get("url") and "reddit.com" not in p["url"]:
            text = f"Links to: {p['url']}"
        thumb = p.get("thumbnail")
        out.append(
            Signal(
                id=Signal.make_id("reddit", url),
                source="reddit",
                source_label=f"r/{p.get('subreddit', '')}",
                title=clean(p.get("title"), 300),
                url=url,
                text=text,
                published=datetime.fromtimestamp(p["created_utc"], tz=timezone.utc) if p.get("created_utc") else None,
                score=float(p.get("score", 0)),
                metrics={"upvotes": p.get("score", 0), "comments": p.get("num_comments", 0)},
                image_url=thumb if thumb and str(thumb).startswith("http") else None,
                tags=[p["flair"]] if p.get("flair") else [],
            )
        )
    for e in data.get("errors", []) or []:
        log.warning("reddit export error: %s", e)
    log.info("reddit: %d posts from %s", len(out), path.name)
    return out
