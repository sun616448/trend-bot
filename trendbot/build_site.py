"""Render data/ into a static site (site/) for GitHub Pages."""
from __future__ import annotations

import json
import shutil
from datetime import date, datetime, timedelta
from pathlib import Path
from urllib.parse import urlparse

from jinja2 import Environment, FileSystemLoader, select_autoescape

from trendbot.models import Signal, WeekRecord

ROOT = Path(__file__).resolve().parent.parent
SECTION_META = {
    "products": ("Products", "What people are buying, coveting or complaining about"),
    "digital": ("Digital", "Apps, AI tools and platform features gaining ground"),
    "campaigns": ("Campaigns", "Activations, stunts and tie-ins that landed or flopped"),
    "culture": ("Culture", "Memes, formats, sounds and discourse brands will ride"),
}
MOMENTUM = {
    "breaking": ("●", "Breaking"),
    "rising": ("▲", "Rising"),
    "peaking": ("◆", "Peaking"),
    "steady": ("■", "Steady"),
}
SOURCE_NAMES = {
    "reddit": "Reddit", "bluesky": "Bluesky", "google_trends": "Google Trends", "hackernews": "Hacker News",
    "producthunt": "Product Hunt", "appstore": "App Store", "rss": "Press", "tiktok": "TikTok", "youtube": "YouTube",
}


def week_range(week: str) -> tuple[date, date]:
    y, w = week.split("-W")
    start = date.fromisocalendar(int(y), int(w), 1)
    return start, start + timedelta(days=6)


def fmt_range(week: str) -> str:
    a, b = week_range(week)
    if a.month == b.month:
        return f"{a:%b} {a.day}–{b.day}, {b.year}"
    return f"{a:%b} {a.day} – {b:%b} {b.day}, {b.year}"


def domain(url: str) -> str:
    d = urlparse(url).netloc.replace("www.", "")
    return d


def load_weeks(data: Path) -> list[WeekRecord]:
    recs = [WeekRecord.model_validate_json(p.read_text()) for p in sorted((data / "digests").glob("*.json"))]
    return sorted(recs, key=lambda r: r.week, reverse=True)


def load_signals(data: Path, week: str) -> list[Signal]:
    p = data / "raw" / f"{week}.json"
    if not p.exists():
        return []
    from trendbot.rank import rank

    return rank([Signal.model_validate(d) for d in json.loads(p.read_text())])


def build(data: Path, out: Path) -> None:
    env = Environment(loader=FileSystemLoader(ROOT / "templates"), autoescape=select_autoescape(["html"]))
    env.filters["domain"] = domain
    env.filters["fmt_range"] = fmt_range
    env.globals.update(SECTION_META=SECTION_META, MOMENTUM=MOMENTUM, SOURCE_NAMES=SOURCE_NAMES)

    if out.exists():
        shutil.rmtree(out)
    (out / "weeks").mkdir(parents=True)
    shutil.copytree(ROOT / "static", out / "static")
    if (data / "media").exists():
        shutil.copytree(data / "media", out / "media")

    weeks = load_weeks(data)
    week_tpl, signals_tpl = env.get_template("week.html"), env.get_template("signals.html")
    for i, rec in enumerate(weeks):
        signals = load_signals(data, rec.week)
        ctx = dict(rec=rec, weeks=weeks, signals=signals, is_latest=(i == 0), built=datetime.now(),
                   tiktok_shot=(data / "media" / rec.week / "tiktok-creative-center.png").exists())
        html = week_tpl.render(root="../", **ctx)
        (out / "weeks" / f"{rec.week}.html").write_text(html)
        (out / "weeks" / f"{rec.week}-signals.html").write_text(signals_tpl.render(root="../", **ctx))
        if i == 0:
            (out / "index.html").write_text(week_tpl.render(root="./", **ctx))
    if not weeks:
        (out / "index.html").write_text(env.get_template("empty.html").render(root="./"))
    (out / ".nojekyll").write_text("")
    print(f"site: {len(weeks)} week(s) -> {out}")
