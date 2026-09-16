"""Run every collector, tolerate individual failures, persist raw signals."""
from __future__ import annotations

import json
from pathlib import Path

from trendbot.collectors import appstore, bluesky, google_trends, hackernews, producthunt, reddit, rss, tiktok, youtube
from trendbot.collectors.base import log
from trendbot.models import Signal

COLLECTORS = {
    "reddit": reddit.collect,
    "bluesky": bluesky.collect,
    "google_trends": google_trends.collect,
    "hackernews": hackernews.collect,
    "producthunt": producthunt.collect,
    "appstore": appstore.collect,
    "rss": rss.collect,
    "youtube": youtube.collect,
}


def collect_all(media_dir: Path, only: set[str] | None = None) -> tuple[list[Signal], list[str]]:
    signals: list[Signal] = []
    notes: list[str] = []
    for name, fn in COLLECTORS.items():
        if only and name not in only:
            continue
        try:
            got = fn()
            signals.extend(got)
            if not got:
                notes.append(f"{name}: returned no signals")
        except Exception as e:  # noqa: BLE001
            log.exception("collector %s failed", name)
            notes.append(f"{name}: failed ({type(e).__name__}: {e})")
    if not only or "tiktok" in only:
        try:
            got = tiktok.collect(screenshot_path=media_dir / "tiktok-creative-center.png")
            signals.extend(got)
            if not got:
                notes.append("tiktok: returned no signals")
        except Exception as e:  # noqa: BLE001
            log.exception("collector tiktok failed")
            notes.append(f"tiktok: failed ({e})")
    # dedupe by url across sources (keep the higher-scoring copy)
    seen: dict[str, Signal] = {}
    for s in signals:
        key = s.url.rstrip("/").lower()
        if key not in seen or s.score > seen[key].score:
            seen[key] = s
    return list(seen.values()), notes


def save_raw(signals: list[Signal], path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps([s.model_dump(mode="json") for s in signals], indent=1, ensure_ascii=False))


def load_raw(path: Path) -> list[Signal]:
    return [Signal.model_validate(d) for d in json.loads(path.read_text())]
