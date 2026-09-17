# Trend Pulse

A weekly "what is everyone talking about" digest for people in marketing, brand and
consumer product. Every Monday a GitHub Actions job collects signals from places where
people actually talk, asks Claude to write a four-section digest, grabs pictures, and
publishes a static dashboard to GitHub Pages with an archive of past weeks.

Sections: **Products**, **Digital**, **Campaigns**, **Culture**, plus an events radar.

## Sources (all free)

| Source | How | Needs a key |
|---|---|---|
| Reddit (43 subreddits, top of week) | Companion Devvit app in `devvit/` exports to `data/reddit/` weekly | Devvit login + a GitHub token in the app's settings |
| Bluesky | Public search API | no |
| TikTok Creative Center | Headless browser reads the US 7-day hashtag table and screenshots it | no |
| Google Trends | Daily trending searches RSS (US) | no |
| Hacker News | Algolia API, front page of the week | no |
| Product Hunt | Public feed | no |
| App Store top free (US) | Apple marketing RSS | no |
| Trade and culture press (36 feeds) | RSS | no |
| YouTube most popular (US) | Data API v3 | `YOUTUBE_API_KEY` (optional) |

Reddit closed self-serve API keys in 2026 and blocks anonymous JSON and RSS from cloud
networks, so Reddit signal comes from a small Devvit app that runs inside Reddit. See
`devvit/README.md` for the one-time setup. Everything else works without keys.

## Run locally

```bash
uv sync
uv run playwright install chromium
export ANTHROPIC_API_KEY=...          # digest step

uv run trendbot run                   # collect -> rank -> digest -> media -> site/
uv run trendbot run --skip-llm        # everything except the Claude step
uv run trendbot collect --only rss,bluesky
uv run trendbot build                 # rebuild site/ from data/
python -m http.server -d site 8000    # preview at http://localhost:8000
```

Weeks are keyed by ISO week (`2026-W38`). Raw signals live in `data/raw/`, the digest and
media map in `data/digests/`, images in `data/media/<week>/`. These are committed by the
workflow so the archive persists; `site/` is built fresh each run and deployed.

## Deploy

1. Push to GitHub, then in the repo settings under **Pages** set the source to **GitHub Actions**.
2. Add repository secrets: `ANTHROPIC_API_KEY`, and optionally `YOUTUBE_API_KEY`.
3. Run the workflow once by hand from the Actions tab. After that it runs every Monday.

## Tuning

- `trendbot/config.py` holds the subreddit list, RSS feeds, Bluesky queries and keyword
  hints. Add or remove freely.
- `trendbot/digest.py` holds the editorial prompt and the model (`TRENDBOT_MODEL`,
  default `claude-opus-5`).
- `templates/` and `static/style.css` are the dashboard.

Each weekly run costs roughly a dollar in Claude usage at current Opus pricing.
