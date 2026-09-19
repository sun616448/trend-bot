"""Turn a pile of signals into a bounded, ordered list for the digest prompt.

Scores are not comparable across sources (upvotes vs. views vs. feed position), so each
source is normalised to 0..1 by rank within that source, then boosted when the same
story shows up in more than one place or matches section keywords.
"""
from __future__ import annotations

import math
import re
from collections import defaultdict

from trendbot.config import PER_SOURCE_CAP, SECTION_KEYWORDS
from trendbot.models import Signal

# Signals mentioning these are pushed down, not removed: the digest is about brands and consumers.
NOISE = [
    "trump", "biden", "vance", "maga", "democrat", "republican", "congress", "senate", "election", "israel", "gaza",
    "ukraine", "putin", "epstein", "shooting", "murder", "nsfw", "lewd", "freaky", "porn", "onlyfans", "gangbang",
    "bestiality", "furry", "fursuit", "commission", "commissions open",
]

STOP = set("the a an and or of to in on for with is are was be this that it its at by from as new how why what".split())


def _terms(s: Signal) -> set[str]:
    words = re.findall(r"[a-z0-9][a-z0-9'-]{2,}", (s.title + " " + s.text[:200]).lower())
    return {w for w in words if w not in STOP}


def _keyword_hits(s: Signal) -> int:
    blob = (s.title + " " + s.text).lower()
    return sum(1 for kws in SECTION_KEYWORDS.values() for kw in kws if kw in blob)


def rank(signals: list[Signal]) -> list[Signal]:
    by_source: dict[str, list[Signal]] = defaultdict(list)
    for s in signals:
        by_source[s.source].append(s)

    scored: list[tuple[float, Signal]] = []
    for src, items in by_source.items():
        # rss, reddit and tiktok are many feeds/subs/lists: rank inside each so one loud group can't dominate
        groups: dict[str, list[Signal]] = defaultdict(list)
        for s in items:
            if src == "bluesky":
                groups[str(s.metrics.get("query", "bluesky"))].append(s)
            elif src in ("rss", "reddit"):
                groups[s.source_label].append(s)
            elif src == "tiktok":   # overall top 100, one list per industry, trending videos
                groups[str(s.metrics.get("group", "overall"))].append(s)
            else:
                groups[src].append(s)
        for _, grp in groups.items():
            grp.sort(key=lambda s: (-(s.score or 0), s.rank or 999))
            n = max(len(grp), 1)
            for i, s in enumerate(grp):
                base = 1.0 - i / n
                if s.score:
                    base += 0.15 * math.log10(1 + s.score) / 6   # small nudge for absolute size
                base += 0.05 * min(_keyword_hits(s), 4)
                blob = (s.title + " " + s.text).lower()
                if any(n in blob for n in NOISE):
                    base -= 0.6
                scored.append((base, s))

    # cross-source echo: signals sharing 3+ distinctive terms with a signal from a different source
    terms = {s.id: _terms(s) for _, s in scored}
    index: dict[str, set[str]] = defaultdict(set)
    for sid, ts in terms.items():
        for t in ts:
            index[t].add(sid)
    src_of = {s.id: s.source_label for _, s in scored}
    boosted: list[tuple[float, Signal]] = []
    for score, s in scored:
        overlap: dict[str, int] = defaultdict(int)
        for t in terms[s.id]:
            if len(index[t]) > 60:      # too common to mean anything
                continue
            for other in index[t]:
                if other != s.id and src_of[other] != s.source_label:
                    overlap[other] += 1
        echoes = sum(1 for v in overlap.values() if v >= 3)
        boosted.append((score + 0.12 * min(echoes, 5), s))

    # cap per source, then global order
    per_source: dict[str, int] = defaultdict(int)
    boosted.sort(key=lambda t: -t[0])
    out: list[Signal] = []
    for score, s in boosted:
        if per_source[s.source] >= PER_SOURCE_CAP * {"rss": 3, "reddit": 3, "tiktok": 2}.get(s.source, 1):
            continue
        per_source[s.source] += 1
        s.metrics["rank_score"] = round(score, 3)
        out.append(s)
    return out
