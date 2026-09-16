"""TikTok Creative Center trending hashtags (US, last 7 days).

Logged out, TikTok renders only the top hashtags server-side, so this collector drives
a headless browser, reads the table, and keeps a screenshot of the page as media.
"""
from __future__ import annotations

import re
from pathlib import Path

from trendbot.collectors.base import log
from trendbot.config import BROWSER_UA
from trendbot.models import Signal

URL = "https://ads.tiktok.com/business/creativecenter/inspiration/popular/hashtag/pc/en"


def _num(s: str) -> float:
    s = s.strip().upper().replace(",", "")
    m = re.match(r"([\d.]+)([KMB]?)", s)
    if not m:
        return 0.0
    n = float(m.group(1))
    return n * {"": 1, "K": 1e3, "M": 1e6, "B": 1e9}[m.group(2)]


def collect(screenshot_path: Path | None = None) -> list[Signal]:
    try:
        from playwright.sync_api import sync_playwright
    except ImportError:
        log.warning("tiktok: playwright not installed")
        return []
    out: list[Signal] = []
    try:
        with sync_playwright() as p:
            browser = p.chromium.launch()
            ctx = browser.new_context(user_agent=BROWSER_UA, locale="en-US", viewport={"width": 1280, "height": 1000})
            page = ctx.new_page()
            page.goto(URL, wait_until="domcontentloaded", timeout=60_000)
            page.wait_for_timeout(8_000)
            body = page.evaluate("() => document.body.innerText")
            if screenshot_path:
                screenshot_path.parent.mkdir(parents=True, exist_ok=True)
                page.screenshot(path=str(screenshot_path), clip={"x": 0, "y": 680, "width": 1280, "height": 520})
            browser.close()
    except Exception as e:  # noqa: BLE001
        log.warning("tiktok: %s", e)
        return []
    # rows look like: "1 | #tag | Category | 37.7K | Posts | 347.2M | Views"
    flat = " | ".join(body.split("\n"))
    for m in re.finditer(r"(\d+) \| (#\S+) \| (?:([^|]+?) \| )?([\d.]+[KMB]?) \| Posts \| ([\d.]+[KMB]?) \| Views", flat):
        rank, tag, cat, posts, views = m.groups()
        url = f"https://www.tiktok.com/tag/{tag.lstrip('#')}"
        out.append(
            Signal(
                id=Signal.make_id("tiktok", url),
                source="tiktok",
                source_label="TikTok Creative Center (US, 7d)",
                title=f"{tag} trending on TikTok",
                url=url,
                text=f"{posts} posts, {views} views in the last 7 days. Category: {cat.strip() if cat else 'n/a'}.",
                rank=int(rank),
                score=_num(views),
                metrics={"posts": posts, "views": views, "category": (cat or "").strip()},
            )
        )
    log.info("tiktok: %d hashtags", len(out))
    return out
