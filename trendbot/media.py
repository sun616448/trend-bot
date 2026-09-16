"""Pictures for the dashboard: source thumbnails when we have them, else a page screenshot."""
from __future__ import annotations

import hashlib
import re
from pathlib import Path
from urllib.parse import urlparse

import httpx

from trendbot.collectors.base import log
from trendbot.config import BROWSER_UA
from trendbot.models import Digest, Signal

MAX_BYTES = 4_000_000
# hosts that block or paywall headless browsers; a screenshot would just be a wall
SKIP_SCREENSHOT = ("reddit.com", "tiktok.com", "instagram.com", "x.com", "twitter.com", "nytimes.com", "theinformation.com", "producthunt.com")
BOT_WALL = ("verify you are human", "security verification", "access denied", "are you a robot", "just a moment", "enable javascript and cookies")


def _slug(s: str) -> str:
    return hashlib.sha1(s.encode()).hexdigest()[:10]


def _download(url: str, dest: Path) -> bool:
    try:
        with httpx.Client(headers={"User-Agent": BROWSER_UA, "Referer": f"https://{urlparse(url).netloc}/"}, timeout=20, follow_redirects=True) as c:
            r = c.get(url)
        if r.status_code != 200 or not r.headers.get("content-type", "").startswith("image"):
            return False
        if len(r.content) > MAX_BYTES or len(r.content) < 2_000:
            return False
        ext = {"image/png": ".png", "image/webp": ".webp", "image/gif": ".gif"}.get(r.headers["content-type"].split(";")[0], ".jpg")
        dest.with_suffix(ext).write_bytes(r.content)
        return True
    except Exception as e:  # noqa: BLE001
        log.debug("image download failed %s: %s", url, e)
        return False


OG_RE = re.compile(r'<meta[^>]+(?:property|name)=["\'](?:og:image|twitter:image)(?::secure_url)?["\'][^>]+content=["\']([^"\']+)["\']', re.I)
OG_RE2 = re.compile(r'<meta[^>]+content=["\']([^"\']+)["\'][^>]+(?:property|name)=["\'](?:og:image|twitter:image)["\']', re.I)


def _og_image(url: str) -> str | None:
    """The page's own social-share image. Almost every article and product page has one."""
    try:
        with httpx.Client(headers={"User-Agent": BROWSER_UA, "Accept": "text/html"}, timeout=15, follow_redirects=True) as c:
            r = c.get(url)
        if r.status_code != 200 or "html" not in r.headers.get("content-type", ""):
            return None
        head = r.text[:200_000]
        m = OG_RE.search(head) or OG_RE2.search(head)
        if not m:
            return None
        img = m.group(1)
        if img.startswith("//"):
            img = "https:" + img
        elif img.startswith("/"):
            u = urlparse(str(r.url))
            img = f"{u.scheme}://{u.netloc}{img}"
        return img
    except Exception as e:  # noqa: BLE001
        log.debug("og:image failed %s: %s", url, e)
        return None


def _find(dest_stem: Path) -> str | None:
    for p in dest_stem.parent.glob(dest_stem.name + ".*"):
        return p.name
    return None


def capture(digest: Digest, signals: list[Signal], media_dir: Path, max_screens: int = 40) -> dict[str, str]:
    """Returns {item_key: filename} where item_key = f'{section}:{index}'."""
    media_dir.mkdir(parents=True, exist_ok=True)
    by_url = {s.url: s for s in signals}
    result: dict[str, str] = {}
    to_shoot: list[tuple[str, str]] = []

    for sec in digest.sections:
        for i, it in enumerate(sec.items):
            key = f"{sec.key}:{i}"
            candidates = [it.hero_url] if it.hero_url else []
            candidates += [r.url for r in it.sources]
            dest = media_dir / _slug(key + (it.hero_url or ""))
            if existing := _find(dest):
                result[key] = existing
                continue
            # 1. the hero link's own thumbnail; 2. its og:image; 3. a screenshot of the hero link;
            # 4. a thumbnail from a secondary source; 5. a screenshot of a secondary source.
            hero = candidates[0]
            hs = by_url.get(hero)
            if hs and hs.image_url and _download(hs.image_url, dest):
                result[key] = _find(dest) or ""
                continue
            og = _og_image(hero)
            if og and _download(og, dest):
                result[key] = _find(dest) or ""
                continue
            if not any(h in hero for h in SKIP_SCREENSHOT):
                to_shoot.append((key, hero))
                continue
            done = False
            for u in candidates[1:]:
                s = by_url.get(u)
                if s and s.image_url and _download(s.image_url, dest):
                    result[key] = _find(dest) or ""
                    done = True
                    break
            if done:
                continue
            for u in candidates[1:]:
                if not any(h in u for h in SKIP_SCREENSHOT):
                    to_shoot.append((key, u))
                    break

    if to_shoot:
        _screenshot_all(to_shoot[:max_screens], media_dir, result)
    return result


def _screenshot_all(items: list[tuple[str, str]], media_dir: Path, result: dict[str, str]) -> None:
    try:
        from playwright.sync_api import sync_playwright
    except ImportError:
        log.warning("media: playwright missing, no screenshots")
        return
    with sync_playwright() as p:
        browser = p.chromium.launch()
        ctx = browser.new_context(user_agent=BROWSER_UA, locale="en-US", viewport={"width": 1200, "height": 750}, device_scale_factor=1)
        page = ctx.new_page()
        page.route(re.compile(r".*\.(mp4|webm|m3u8)"), lambda r: r.abort())
        for key, url in items:
            dest = media_dir / (_slug(key + url) + ".jpg")
            try:
                page.goto(url, wait_until="domcontentloaded", timeout=30_000)
                page.wait_for_timeout(2_500)
                _dismiss_banners(page)
                text = (page.evaluate("() => document.body.innerText") or "")[:2000].lower()
                if any(w in text for w in BOT_WALL):
                    log.info("screenshot skipped (bot wall) %s", url)
                    continue
                page.screenshot(path=str(dest), type="jpeg", quality=70)
                result[key] = dest.name
            except Exception as e:  # noqa: BLE001
                log.warning("screenshot failed %s: %s", url, str(e)[:100])
        browser.close()


def _dismiss_banners(page) -> None:
    for sel in ("button:has-text('Accept all')", "button:has-text('Accept All')", "button:has-text('Accept')", "button:has-text('I agree')", "button:has-text('Got it')"):
        try:
            btn = page.locator(sel).first
            if btn.is_visible(timeout=300):
                btn.click(timeout=1000)
                page.wait_for_timeout(300)
                return
        except Exception:  # noqa: BLE001
            pass
