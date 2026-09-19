"""TikTok Creative Center trends (US, last 7 days).

Logged out, TikTok renders only the top few hashtags. Logged in with a free TikTok for
Business account the page is a virtualized, infinite-scrolling top-100 table with an
industry filter, plus a Video tab of trending videos. This collector drives a headless
browser with a saved login session when one exists:

  * locally:  .tiktok_state.json at the repo root, written by `uv run trendbot tiktok-login`
  * in CI:    the TIKTOK_STORAGE_STATE secret, holding the same JSON

Without a session it still returns the logged-out top few and keeps a screenshot.
Set TIKTOK_DEBUG_DIR to dump page text and screenshots while iterating on selectors.
"""
from __future__ import annotations

import json
import os
import re
from pathlib import Path
from urllib.parse import quote

from trendbot.collectors.base import log
from trendbot.config import BROWSER_UA, TIKTOK_INDUSTRIES, TIKTOK_ROWS_PER_INDUSTRY
from trendbot.models import Signal

URL = "https://ads.tiktok.com/business/creativecenter/inspiration/popular/hashtag/pc/en"
LOGIN_URL = URL
STATE_PATH = Path(__file__).resolve().parents[2] / ".tiktok_state.json"
STATE_ENV = "TIKTOK_STORAGE_STATE"
MAX_ROWS = 100
MAX_SCROLLS = 40
SCROLL_STEP = 400
# TikTok for Business suffixes its session cookies with _ads; plain names cover tiktok.com logins.
SESSION_COOKIES = {"sessionid", "sessionid_ss", "sid_tt", "uid_tt", "sessionid_ads", "sessionid_ss_ads", "sid_tt_ads", "uid_tt_ads"}
# "1 | #tag | Industry | Industry2 | 37.7K | Posts | 347.2M | Views" once newlines are joined
ROW_RE = re.compile(r"(\d+) \| (#\S+) \| ((?:[^|\d][^|]*? \| ){0,3})([\d.]+[KMB]?) \| Posts \| ([\d.]+[KMB]?) \| Views")

VIDEO_CARDS_JS = """() => {
  const buttons = [...document.querySelectorAll('*')]
    .filter(e => e.children.length === 0 && e.innerText?.trim() === 'View details');
  const cards = buttons.map(b => {
    let n = b, fallback = null;
    for (let i = 0; i < 10 && n; i++) {
      n = n.parentElement;
      if (!n) break;
      if (n.innerText.split('View details').length !== 2) break;   // climbed into a sibling card
      if (String(n.className).includes('h-[571px]')) return n;      // the card container
      if ([...n.querySelectorAll('img[alt]')].some(i => i.alt.trim())) fallback = n;
    }
    return fallback;
  }).filter(Boolean);
  return cards.map(c => {
    const img = [...c.querySelectorAll('img[alt]')].find(i => i.alt.trim()) || c.querySelector('img[alt]');
    const lines = c.innerText.split('\\n').map(t => t.trim()).filter(Boolean);
    return { caption: img ? img.alt : '', cover: img ? img.src : '', lines };
  });
}"""


def _num(s: str) -> float:
    s = s.strip().upper().replace(",", "")
    m = re.match(r"([\d.]+)([KMB]?)", s)
    if not m:
        return 0.0
    return float(m.group(1)) * {"": 1, "K": 1e3, "M": 1e6, "B": 1e9}[m.group(2)]


# --- session -----------------------------------------------------------------------------


def load_state() -> dict | None:
    """Saved login session as a Playwright storage_state dict, or None."""
    raw = os.environ.get(STATE_ENV, "").strip()
    if raw:
        try:
            return json.loads(raw)
        except json.JSONDecodeError as e:
            log.warning("tiktok: %s is not valid JSON (%s); running logged out", STATE_ENV, e)
    if STATE_PATH.exists():
        try:
            return json.loads(STATE_PATH.read_text())
        except json.JSONDecodeError as e:
            log.warning("tiktok: %s is not valid JSON (%s); running logged out", STATE_PATH.name, e)
    return None


def slim_state(state: dict) -> dict:
    """Keep only TikTok cookies (no localStorage) so the JSON fits in a GitHub secret."""
    keep = lambda host: "tiktok" in host or "bytedance" in host  # noqa: E731
    return {"cookies": [c for c in state.get("cookies", []) if keep(c.get("domain", ""))], "origins": []}


def has_session_cookie(ctx) -> bool:  # noqa: ANN001
    return any(c["name"] in SESSION_COOKIES for c in ctx.cookies())


def is_logged_in(page) -> bool:  # noqa: ANN001
    """On the Creative Center page: the header shows the account instead of a 'Log in' button."""
    return page.evaluate("() => ![...document.querySelectorAll('button, a')].some(e => e.innerText.trim() === 'Log in')")


# --- page scraping -----------------------------------------------------------------------


def parse_rows(body: str) -> dict[str, tuple[int, str, str, str]]:
    """Hashtag rows from the page text: {tag: (rank, industries, posts, views)}."""
    flat = " | ".join(body.split("\n"))
    found = {}
    for m in ROW_RE.finditer(flat):
        rank, tag, cats, posts, views = m.groups()
        cat = ", ".join(c.strip() for c in cats.split("|") if c.strip())  # rows can carry one or two industries
        found[tag] = (int(rank), cat, posts, views)
    return found


def scroll_rows(page, max_rows: int) -> dict[str, tuple[int, str, str, str]]:  # noqa: ANN001
    """Scroll the virtualized table in steps, merging whatever each step renders."""
    rows = parse_rows(page.evaluate("() => document.body.innerText"))
    idle = 0
    for _ in range(MAX_SCROLLS):
        if len(rows) >= max_rows:
            break
        page.mouse.wheel(0, SCROLL_STEP)
        page.wait_for_timeout(1_000)
        before = len(rows)
        rows.update(parse_rows(page.evaluate("() => document.body.innerText")))
        idle = idle + 1 if len(rows) == before else 0
        if idle >= 4:
            break
    page.mouse.wheel(0, -SCROLL_STEP * MAX_SCROLLS)
    page.wait_for_timeout(600)
    return rows


def select_industry(page, name: str) -> bool:  # noqa: ANN001
    """Pick an industry in the first select (the second is the period)."""
    try:
        page.locator(".byted-select-input").first.click(timeout=5_000)
        page.wait_for_timeout(1_000)
        opt = page.locator(".byted-select-popover-panel [data-type=select-option]").filter(has_text=re.compile(rf"^\s*{re.escape(name)}\s*$"))
        if opt.count() == 0:
            page.keyboard.press("Escape")
            log.warning("tiktok: industry %r not in dropdown", name)
            return False
        opt.first.click(timeout=5_000)
        page.wait_for_timeout(3_000)
        return True
    except Exception as e:  # noqa: BLE001
        log.warning("tiktok: selecting industry %r failed: %s", name, e)
        return False


def hashtag_signal(tag: str, rank: int, cat: str, posts: str, views: str, industry_ranks: dict[str, int]) -> Signal:
    url = f"https://www.tiktok.com/tag/{tag.lstrip('#')}"
    where = ", ".join(f"#{r} in {ind}" for ind, r in industry_ranks.items())
    # ranking group: the overall top 100, or the first industry list this tag appeared in
    group = "overall" if rank <= MAX_ROWS else next(iter(industry_ranks), "overall")
    return Signal(
        id=Signal.make_id("tiktok", url),
        source="tiktok",
        source_label="TikTok Creative Center (US, 7d)",
        title=f"{tag} trending on TikTok",
        url=url,
        text=f"{posts} posts, {views} views in the last 7 days. Category: {cat or 'n/a'}."
        + (f" Overall rank #{rank}." if rank <= MAX_ROWS else "")
        + (f" {where}." if where else ""),
        rank=rank,
        score=_num(views),
        metrics={"posts": posts, "views": views, "category": cat, "industry_ranks": where, "kind": "hashtag", "group": group},
    )


def collect_videos(page) -> list[Signal]:  # noqa: ANN001
    """Trending videos from the Video tab: caption (cover image alt), creator, followers, views."""
    page.get_by_text("Video", exact=True).first.click(timeout=5_000)
    page.wait_for_timeout(6_000)
    # covers (whose alt text is the caption) load lazily: scroll the grid once so they all render
    for _ in range(8):
        page.mouse.wheel(0, 700)
        page.wait_for_timeout(600)
    page.wait_for_timeout(2_000)
    page.mouse.wheel(0, -8 * 700)
    page.wait_for_timeout(500)
    out: list[Signal] = []
    seen: set[str] = set()
    for i, card in enumerate(page.evaluate(VIDEO_CARDS_JS), start=1):
        lines: list[str] = card["lines"]
        caption = " ".join((card["caption"] or "").split())
        # lines: [industry?] creator, "N followers", "Video views", "N", "View details"
        fi = next((i for i, t in enumerate(lines) if t.endswith("followers")), -1)
        creator = lines[fi - 1] if fi > 0 else (lines[0] if lines else "")
        industry = lines[0] if fi > 1 else ""
        followers = lines[fi].replace(" followers", "") if fi >= 0 else ""
        views = lines[lines.index("Video views") + 1] if "Video views" in lines and lines.index("Video views") + 1 < len(lines) else ""
        key = caption or creator
        if not key or key in seen:
            continue
        seen.add(key)
        url = f"https://www.tiktok.com/search?q={quote((caption[:80] if caption else creator).strip())}"
        title = caption if len(caption) <= 110 else caption[:110] + "…"
        out.append(
            Signal(
                id=Signal.make_id("tiktok", url),
                source="tiktok",
                source_label="TikTok Creative Center trending videos (US, 7d)",
                title=title or f"Trending video by {creator}",
                url=url,
                text=f"By {creator} ({followers} followers), {views} views in the last 7 days."
                + (f" Industry: {industry}." if industry else "")
                + (f" Caption: {caption}" if caption else ""),
                rank=i,
                score=_num(views),
                metrics={"creator": creator, "followers": followers, "views": views, "industry": industry, "kind": "video", "group": "videos"},
                image_url=card["cover"] or None,
            )
        )
    return out


def collect(screenshot_path: Path | None = None) -> list[Signal]:
    try:
        from playwright.sync_api import sync_playwright
    except ImportError:
        log.warning("tiktok: playwright not installed")
        return []
    state = load_state()
    debug_dir = os.environ.get("TIKTOK_DEBUG_DIR")
    logged_in = False
    overall: dict[str, tuple[int, str, str, str]] = {}
    per_industry: dict[str, dict[str, tuple[int, str, str, str]]] = {}
    videos: list[Signal] = []
    try:
        with sync_playwright() as p:
            browser = p.chromium.launch()
            ctx = browser.new_context(user_agent=BROWSER_UA, locale="en-US", viewport={"width": 1280, "height": 1000}, storage_state=state)
            page = ctx.new_page()
            page.goto(os.environ.get("TIKTOK_URL", URL), wait_until="domcontentloaded", timeout=60_000)
            page.wait_for_timeout(8_000)
            log.debug("tiktok: landed on %s", page.url)
            logged_in = is_logged_in(page)
            if state and not logged_in:
                log.warning("tiktok: saved session was rejected; run `uv run trendbot tiktok-login` again")
            if debug_dir:
                d = Path(debug_dir)
                d.mkdir(parents=True, exist_ok=True)
                (d / "loaded.txt").write_text(page.evaluate("() => document.body.innerText"))
                page.screenshot(path=str(d / "loaded.png"), full_page=True)
            if screenshot_path:
                screenshot_path.parent.mkdir(parents=True, exist_ok=True)
                page.screenshot(path=str(screenshot_path), clip={"x": 0, "y": 680, "width": 1280, "height": 520})
            overall = scroll_rows(page, MAX_ROWS if logged_in else 10)
            if logged_in:
                for name in TIKTOK_INDUSTRIES:
                    if select_industry(page, name):
                        per_industry[name] = scroll_rows(page, TIKTOK_ROWS_PER_INDUSTRY)
                        log.debug("tiktok: %s: %d rows", name, len(per_industry[name]))
                try:
                    videos = collect_videos(page)
                except Exception as e:  # noqa: BLE001
                    log.warning("tiktok: video tab failed: %s", e)
            browser.close()
    except Exception as e:  # noqa: BLE001
        log.warning("tiktok: %s", e)
        return []

    # merge: one signal per hashtag, carrying its rank in each industry list it appeared in
    merged: dict[str, tuple[int, str, str, str]] = dict(overall)
    industry_ranks: dict[str, dict[str, int]] = {}
    for name, rows in per_industry.items():
        for tag, (rank, cat, posts, views) in rows.items():
            industry_ranks.setdefault(tag, {})[name] = rank
            if tag not in merged:
                merged[tag] = (MAX_ROWS + rank, cat or name, posts, views)  # sorts after the overall top 100
    out = [hashtag_signal(tag, r, c, p_, v, industry_ranks.get(tag, {})) for tag, (r, c, p_, v) in sorted(merged.items(), key=lambda kv: kv[1][0])]
    out.extend(videos)
    log.info(
        "tiktok: %d hashtags (%d overall, %d industry-only), %d videos (%s)",
        len(merged), len(overall), len(merged) - len(overall), len(videos), "logged in" if logged_in else "logged out",
    )
    return out


# --- login helpers -----------------------------------------------------------------------


def login(state_path: Path = STATE_PATH, timeout_s: int = 600) -> Path:
    """Open a visible browser, wait for you to log in, then save the session to state_path.

    Login is detected by TikTok's session cookie, or by the Creative Center page no longer
    showing a 'Log in' button. Closing the window early saves whatever cookies exist.
    """
    from playwright.sync_api import sync_playwright

    def say(msg: str) -> None:
        print(msg, flush=True)

    with sync_playwright() as p:
        # TikTok's login refuses browsers that look automated, so use the real installed Chrome
        # (falling back to bundled Chromium) and drop the automation flags.
        launch = dict(headless=False, args=["--disable-blink-features=AutomationControlled"], ignore_default_args=["--enable-automation"])
        try:
            browser = p.chromium.launch(channel="chrome", **launch)
        except Exception:  # noqa: BLE001  (no Chrome installed)
            browser = p.chromium.launch(**launch)
        ctx = browser.new_context(locale="en-US", viewport={"width": 1280, "height": 1000})
        ctx.add_init_script("Object.defineProperty(navigator, 'webdriver', {get: () => undefined})")
        page = ctx.new_page()
        page.goto(LOGIN_URL, wait_until="domcontentloaded", timeout=60_000)
        say("A browser window is open. Click 'Log in' and sign in with your TikTok for Business account.")
        say("Waiting for the login to complete (up to %d minutes)..." % (timeout_s // 60))
        waited = 0
        state: dict | None = None
        while waited < timeout_s:
            try:
                page.wait_for_timeout(2_000)
                names = {c["name"] for c in ctx.cookies()}
                on_center = "creativecenter" in page.url.lower()
                if has_session_cookie(ctx) or (on_center and len(names) > 5 and is_logged_in(page)):
                    say("Login detected, saving the session...")
                    page.wait_for_timeout(3_000)  # let post-login cookies settle
                    state = slim_state(ctx.storage_state())
                    break
            except Exception as e:  # noqa: BLE001
                if "closed" in str(e).lower():
                    say("Browser window was closed; saving whatever cookies were set.")
                    try:
                        state = slim_state(ctx.storage_state())
                    except Exception:  # noqa: BLE001
                        state = None
                    break
                continue  # page mid-navigation
            waited += 2
        else:
            say("Timed out waiting for login; saving whatever cookies were set.")
            state = slim_state(ctx.storage_state())
        try:
            browser.close()
        except Exception:  # noqa: BLE001
            pass
    if not state or not state["cookies"]:
        raise SystemExit("no TikTok cookies were captured; nothing saved")
    state_path.write_text(json.dumps(state))
    names = sorted(c["name"] for c in state["cookies"])
    say(f"Saved {len(names)} cookies: {', '.join(names)}")
    if not any(n in SESSION_COOKIES for n in names):
        say("Note: none of the expected session cookie names were present; the collector will report whether the session works.")
    return state_path


def import_cookies(path: Path, state_path: Path = STATE_PATH) -> Path:
    """Build the session file from cookies exported by a browser extension.

    Accepts Netscape cookies.txt (e.g. the "Get cookies.txt LOCALLY" extension) or a JSON
    array of {name, value, domain, path, ...} (e.g. Cookie-Editor export). Export while
    signed in to ads.tiktok.com.
    """
    text = path.read_text()
    cookies: list[dict] = []
    if text.lstrip().startswith("["):
        for c in json.loads(text):
            cookies.append(
                {
                    "name": c["name"],
                    "value": c["value"],
                    "domain": c.get("domain", ".tiktok.com"),
                    "path": c.get("path", "/"),
                    "expires": float(c.get("expirationDate") or c.get("expires") or -1),
                    "httpOnly": bool(c.get("httpOnly", False)),
                    "secure": bool(c.get("secure", True)),
                    "sameSite": "None",
                }
            )
    else:
        for line in text.splitlines():
            if not line or line.startswith("#"):
                continue
            parts = line.split("\t")
            if len(parts) < 7:
                continue
            domain, _flag, cpath, secure, expires, name, value = parts[:7]
            cookies.append(
                {"name": name, "value": value, "domain": domain, "path": cpath, "expires": float(expires or -1), "httpOnly": False, "secure": secure.upper() == "TRUE", "sameSite": "None"}
            )
    state = slim_state({"cookies": cookies, "origins": []})
    if not any(c["name"] in SESSION_COOKIES for c in state["cookies"]):
        raise SystemExit(f"no TikTok session cookie found in {path}; export while signed in to ads.tiktok.com")
    state_path.write_text(json.dumps(state))
    return state_path
