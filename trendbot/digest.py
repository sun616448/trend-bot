"""Ask Claude to turn ranked signals into the weekly digest (structured output)."""
from __future__ import annotations

import json
import os
from datetime import date

import anthropic

from trendbot.collectors.base import log
from trendbot.models import Digest, Signal

MODEL = os.environ.get("TRENDBOT_MODEL", "claude-opus-5")

SYSTEM = """You are the editor of a weekly trend digest for people who work in marketing, brand and consumer product. \
Your readers want to know what consumers are actually talking about this week, not press-release news.

You will receive a list of signals collected this week from Reddit, Bluesky, TikTok Creative Center, Google Trends, \
Hacker News, Product Hunt, the App Store chart and trade press RSS. Each signal has an id, a source, a URL and text.

Write the digest with four sections, in this order and with these keys:
1. products: new or suddenly hot consumer products. Beauty, fashion, food and drink, home, wellness, anything you can buy. \
   Sold-out drops, viral products, notable launches, collabs.
2. digital: apps, AI tools, platform features and digital products people are adopting or arguing about.
3. campaigns: marketing campaigns, brand activations, stunts, pop-ups, sponsorships and event tie-ins \
   (fashion weeks, sports, award shows, holidays). Say what the brand did and why it worked or flopped.
4. culture: memes, formats, sounds, aesthetics, slang, discourse and creator trends that brands end up riding.

Rules:
- Five to eight items per section, ordered by how much people are talking about them. Fewer if the signals are thin.
- Prefer items that appear in more than one source, or that have strong engagement from real people (Reddit, Bluesky, TikTok, Google Trends) \
  over items that only appear in trade press.
- Every item must cite one to five sources using URLs copied exactly from the signals. Never invent a URL or a fact that is not in the signals. \
  You may add brief background you are confident about, but the news itself must come from the signals.
- hero_url is the URL that would make the best picture: a product page, a campaign article, a post. Copy it exactly from the signals.
- what_people_say: short quotes or close paraphrases of actual reactions from the signals, when available. Do not fabricate quotes.
- Write plainly and specifically. Name brands and products. No hype adjectives, no filler.
- The radar lists things coming in the next three weeks that brands will activate around: events, holidays, launches, seasons. \
  Ground it in today's date.
- Ignore politics, crime, disasters and celebrity gossip unless a brand or product is directly involved.
"""


def _format_signals(signals: list[Signal]) -> str:
    lines = []
    for s in signals:
        m = {k: v for k, v in s.metrics.items() if k not in ("rank_score",)}
        meta = ", ".join(f"{k}={v}" for k, v in m.items() if v not in ("", None))
        pub = s.published.strftime("%b %d") if s.published else ""
        lines.append(
            f"[{s.id}] ({s.source} · {s.source_label}{' · ' + pub if pub else ''}{' · ' + meta if meta else ''})\n"
            f"  title: {s.title}\n  url: {s.url}\n" + (f"  text: {s.text}\n" if s.text else "")
        )
    return "\n".join(lines)


def generate(signals: list[Signal], week: str) -> tuple[Digest, str]:
    """Returns (digest, model_that_served)."""
    client = anthropic.Anthropic()
    today = date.today().strftime("%A %B %d, %Y")
    user = (
        f"Today is {today}. This is week {week}. Here are {len(signals)} signals collected over the last seven days, "
        f"roughly ordered by our own ranking (cross-source echoes and engagement).\n\n{_format_signals(signals)}"
    )
    log.info("digest: sending %d signals (%d chars) to %s", len(signals), len(user), MODEL)
    with client.beta.messages.stream(
        model=MODEL,
        max_tokens=48_000,
        system=SYSTEM,
        messages=[{"role": "user", "content": user}],
        output_format=Digest,
        output_config={"effort": "high"},
        betas=["server-side-fallback-2026-07-01"],
        fallbacks="default",
    ) as stream:
        msg = stream.get_final_message()
    if msg.stop_reason == "refusal":
        raise RuntimeError(f"model declined the request: {getattr(msg, 'stop_details', None)}")
    if msg.stop_reason == "max_tokens":
        raise RuntimeError("digest truncated at max_tokens")
    digest = msg.parsed_output
    if digest is None:
        text = "".join(b.text for b in msg.content if b.type == "text")
        digest = Digest.model_validate(json.loads(text))
    usage = msg.usage
    log.info("digest: done. model=%s in=%s out=%s", msg.model, usage.input_tokens, usage.output_tokens)
    return _sanitise(digest, signals), msg.model


def _sanitise(d: Digest, signals: list[Signal]) -> Digest:
    """Drop any source URL that is not in the input, so the digest can never link to a made-up page."""
    known = {s.url for s in signals}
    for sec in d.sections:
        for it in sec.items:
            it.sources = [r for r in it.sources if r.url in known]
            if it.hero_url and it.hero_url not in known:
                it.hero_url = it.sources[0].url if it.sources else None
        sec.items = [it for it in sec.items if it.sources]
    return d
