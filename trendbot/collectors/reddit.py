"""Reddit: OAuth client-credentials when REDDIT_CLIENT_ID/SECRET are set, else the
public old.reddit.com JSON listing (works from most networks with a descriptive UA)."""
from __future__ import annotations

import os
import time

from trendbot.collectors.base import clean, client, get_json, log, ts_to_dt
from trendbot.config import PER_SUBREDDIT, SUBREDDITS
from trendbot.models import Signal


def _token() -> str | None:
    cid, secret = os.environ.get("REDDIT_CLIENT_ID"), os.environ.get("REDDIT_CLIENT_SECRET")
    if not (cid and secret):
        return None
    with client() as c:
        r = c.post(
            "https://www.reddit.com/api/v1/access_token",
            auth=(cid, secret),
            data={"grant_type": "client_credentials"},
        )
        if r.status_code != 200:
            log.warning("reddit oauth failed: %s %s", r.status_code, r.text[:120])
            return None
        return r.json().get("access_token")


def _post_to_signal(sub: str, d: dict) -> Signal | None:
    if d.get("stickied") or d.get("over_18"):
        return None
    url = "https://www.reddit.com" + d.get("permalink", "")
    img = None
    prev = d.get("preview", {}).get("images")
    if prev:
        img = prev[0].get("source", {}).get("url", "").replace("&amp;", "&") or None
    elif d.get("thumbnail", "").startswith("http"):
        img = d["thumbnail"]
    text = clean(d.get("selftext"))
    if not text and d.get("url") and not d["url"].startswith("https://www.reddit.com"):
        text = f"Links to: {d['url']}"
    return Signal(
        id=Signal.make_id("reddit", url),
        source="reddit",
        source_label=f"r/{d.get('subreddit', sub)}",
        title=clean(d.get("title"), 300),
        url=url,
        text=text,
        published=ts_to_dt(d.get("created_utc")),
        score=float(d.get("score", 0)),
        metrics={"upvotes": d.get("score", 0), "comments": d.get("num_comments", 0), "upvote_ratio": d.get("upvote_ratio", 0)},
        image_url=img,
        tags=[d.get("link_flair_text")] if d.get("link_flair_text") else [],
    )


def collect() -> list[Signal]:
    token = _token()
    out: list[Signal] = []
    subs = [s for group in SUBREDDITS.values() for s in group]
    headers = {"Authorization": f"bearer {token}"} if token else {}
    base = "https://oauth.reddit.com" if token else "https://old.reddit.com"
    failures = 0
    with client(headers=headers) as c:
        for sub in subs:
            limit = 25 if sub in ("all", "popular") else PER_SUBREDDIT
            url = f"{base}/r/{sub}/top{'' if token else '.json'}?t=week&limit={limit}&raw_json=1"
            data = get_json(c, url, retries=0 if not token else 2)
            if not data:
                failures += 1
                if not token and failures >= 3 and not out:
                    log.warning("reddit: anonymous access is blocked from this network. "
                                "Set REDDIT_CLIENT_ID / REDDIT_CLIENT_SECRET (free script app) to use the official API.")
                    break
                continue
            for child in data.get("data", {}).get("children", []):
                s = _post_to_signal(sub, child.get("data", {}))
                if s:
                    out.append(s)
            time.sleep(0.6 if token else 1.2)  # stay well under either rate limit
    log.info("reddit: %d signals from %d subreddits", len(out), len(subs))
    return out
