"""trendbot command line.

  uv run trendbot run                 # collect -> rank -> digest -> media -> build site
  uv run trendbot collect             # just collect and save raw signals
  uv run trendbot digest              # digest from the saved raw signals for this week
  uv run trendbot build               # rebuild the static site from data/
  uv run trendbot tiktok-login        # one-time: sign in to TikTok Creative Center and save the session
  uv run trendbot tiktok-login --cookies-file cookies.txt   # same, from a browser cookie export
Flags: --week 2026-W38  --skip-llm  --skip-media  --only reddit,rss
"""
from __future__ import annotations

import argparse
import logging
import sys
from datetime import date
from pathlib import Path

from trendbot.models import WeekRecord, now_utc

ROOT = Path(__file__).resolve().parent.parent
DATA = ROOT / "data"
SITE = ROOT / "site"


def iso_week(d: date | None = None) -> str:
    y, w, _ = (d or date.today()).isocalendar()
    return f"{y}-W{w:02d}"


def cmd_collect(week: str, only: set[str] | None) -> None:
    from trendbot.collect import collect_all, save_raw

    media_dir = DATA / "media" / week
    signals, notes = collect_all(media_dir, only=only)
    save_raw(signals, DATA / "raw" / f"{week}.json")
    rec_path = DATA / "digests" / f"{week}.json"
    rec = WeekRecord.model_validate_json(rec_path.read_text()) if rec_path.exists() else WeekRecord(week=week, generated_at=now_utc())
    rec.signal_count = len(signals)
    counts: dict[str, int] = {}
    for s in signals:
        counts[s.source] = counts.get(s.source, 0) + 1
    rec.source_counts = counts
    rec.notes = notes
    rec_path.parent.mkdir(parents=True, exist_ok=True)
    rec_path.write_text(rec.model_dump_json(indent=1))
    logging.getLogger("trendbot").info("collected %d signals: %s", len(signals), counts)
    for n in notes:
        logging.getLogger("trendbot").warning(n)


def cmd_digest(week: str, skip_llm: bool, skip_media: bool) -> None:
    from trendbot.collect import load_raw
    from trendbot.rank import rank

    raw_path = DATA / "raw" / f"{week}.json"
    if not raw_path.exists():
        sys.exit(f"no raw signals for {week}; run `trendbot collect` first")
    signals = rank(load_raw(raw_path))
    rec_path = DATA / "digests" / f"{week}.json"
    rec = WeekRecord.model_validate_json(rec_path.read_text()) if rec_path.exists() else WeekRecord(week=week, generated_at=now_utc(), signal_count=len(signals))
    if not skip_llm:
        from trendbot.digest import generate

        rec.digest, rec.model = generate(signals, week)
        rec.generated_at = now_utc()
    if rec.digest and not skip_media:
        from trendbot.media import capture

        rec.media = capture(rec.digest, signals, DATA / "media" / week)
    rec_path.write_text(rec.model_dump_json(indent=1))


def cmd_build() -> None:
    from trendbot.build_site import build

    build(DATA, SITE)


def cmd_tiktok_login(cookies_file: str | None) -> None:
    from trendbot.collectors.tiktok import STATE_ENV, import_cookies, login

    path = import_cookies(Path(cookies_file)) if cookies_file else login()
    print(f"\nSaved login session to {path.name} ({path.stat().st_size:,} bytes; gitignored).")
    print("To use it in GitHub Actions, store the file as a repository secret:")
    print(f"  gh secret set {STATE_ENV} < {path.name}")
    print("Sessions expire after a few weeks; rerun this command when the digest notes say the session was rejected.")


def main(argv: list[str] | None = None) -> None:
    ap = argparse.ArgumentParser(prog="trendbot", description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("command", choices=["run", "collect", "digest", "build", "tiktok-login"])
    ap.add_argument("--week", default=iso_week())
    ap.add_argument("--skip-llm", action="store_true", help="do not call Claude (site shows raw signals only)")
    ap.add_argument("--skip-media", action="store_true", help="no screenshots or image downloads")
    ap.add_argument("--only", help="comma-separated collector names")
    ap.add_argument("--cookies-file", help="tiktok-login: build the session from a cookies.txt or JSON export instead of opening a browser")
    ap.add_argument("-v", "--verbose", action="store_true")
    a = ap.parse_args(argv)
    logging.basicConfig(level=logging.DEBUG if a.verbose else logging.INFO, format="%(asctime)s %(levelname)s %(message)s", datefmt="%H:%M:%S")
    logging.getLogger("httpx").setLevel(logging.WARNING)
    only = set(a.only.split(",")) if a.only else None

    if a.command == "tiktok-login":
        cmd_tiktok_login(a.cookies_file)
        return
    if a.command in ("run", "collect"):
        cmd_collect(a.week, only)
    if a.command in ("run", "digest"):
        cmd_digest(a.week, a.skip_llm, a.skip_media)
    if a.command in ("run", "build"):
        cmd_build()


if __name__ == "__main__":
    main()
