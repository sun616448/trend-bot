from __future__ import annotations

import hashlib
from datetime import datetime, timezone
from typing import Literal

from pydantic import BaseModel, Field

Source = Literal[
    "reddit", "bluesky", "google_trends", "hackernews", "producthunt",
    "appstore", "rss", "tiktok", "youtube",
]


class Signal(BaseModel):
    """One thing people are talking about, from one source."""

    id: str
    source: Source
    source_label: str          # e.g. "r/SkincareAddiction", "Adweek", "TikTok Creative Center"
    title: str
    url: str
    text: str = ""             # body / snippet / description, trimmed
    published: datetime | None = None
    score: float = 0.0         # raw engagement number from the source (upvotes, points, views...)
    rank: int | None = None    # position in the source's own ranking, 1 = top
    metrics: dict[str, float | int | str] = Field(default_factory=dict)
    image_url: str | None = None
    tags: list[str] = Field(default_factory=list)

    @staticmethod
    def make_id(source: str, url: str) -> str:
        return hashlib.sha1(f"{source}|{url}".encode()).hexdigest()[:12]


class SourceRef(BaseModel):
    label: str = Field(description="Where this came from, e.g. 'r/SkincareAddiction' or 'Adweek'")
    url: str = Field(description="Exact URL copied from the signals provided")


class DigestItem(BaseModel):
    title: str = Field(description="Short, specific headline. Name the product, brand, campaign or format.")
    summary: str = Field(description="Two to four sentences: what it is and why people are talking about it this week.")
    why_it_matters: str = Field(description="One or two sentences: the takeaway for someone in marketing or product.")
    what_people_say: list[str] = Field(
        default_factory=list,
        description="Up to three short paraphrases or quotes of real reactions from the signals. Empty if none.",
    )
    momentum: Literal["breaking", "rising", "peaking", "steady"] = Field(
        description="breaking = first appeared this week; rising = growing; peaking = everywhere right now; steady = ongoing"
    )
    tags: list[str] = Field(default_factory=list, description="Two to five lowercase tags, e.g. 'beauty', 'collab', 'ai'")
    hero_url: str | None = Field(
        default=None,
        description="Best single URL to screenshot as the visual for this item: a product page, campaign page, or post. Must be one of the signal URLs.",
    )
    sources: list[SourceRef] = Field(description="One to five signals that back this item. URLs must be copied exactly from the input.")


SectionKey = Literal["products", "digital", "campaigns", "culture"]


class DigestSection(BaseModel):
    key: SectionKey
    title: str
    items: list[DigestItem]


class UpcomingEvent(BaseModel):
    name: str
    when: str = Field(description="Approximate date or date range, e.g. 'Oct 31' or 'late September'")
    angle: str = Field(description="One sentence on how brands typically show up, or what to watch for")


class Digest(BaseModel):
    headline: str = Field(description="One line that captures the week. No colon-style titles.")
    tldr: list[str] = Field(description="Three to five one-sentence bullets summarising the week")
    sections: list[DigestSection] = Field(description="Exactly four sections in order: products, digital, campaigns, culture")
    radar: list[UpcomingEvent] = Field(description="Three to six events, launches or cultural moments coming in the next three weeks that brands will activate around")


class WeekRecord(BaseModel):
    """Everything persisted for one week, in data/digests/<week>.json."""

    week: str                  # ISO week, e.g. 2026-W38
    generated_at: datetime
    model: str | None = None
    digest: Digest | None = None
    signal_count: int = 0
    source_counts: dict[str, int] = Field(default_factory=dict)
    media: dict[str, str] = Field(default_factory=dict)   # item key -> relative image path
    notes: list[str] = Field(default_factory=list)        # collector warnings etc.


def now_utc() -> datetime:
    return datetime.now(timezone.utc)
