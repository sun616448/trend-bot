# trendpulse-reddit (Devvit app)

Reddit closed self-serve API keys in 2026, so this small Devvit app runs inside Reddit
and exports the week's top posts from a fixed list of consumer, beauty, food, tech and
marketing subreddits to the Trend Pulse repo. Every Monday at 11:00 UTC it writes
`data/reddit/<ISO week>.json` via the GitHub contents API. Moderators of the install
subreddit can also trigger it from the subreddit menu ("Trend Pulse: export Reddit top
posts now").

## Fetch Domains

The following domains are requested for this app:

- `api.github.com` - Used to write one JSON file per week into the developer's own
  public GitHub repository (`sun616448/trend-bot`) so a weekly trend digest can include
  what people are discussing on Reddit. Only public post metadata is exported: title,
  permalink, score, comment count, author name, timestamp, flair and the first 600
  characters of self-text. No user or private data is read or sent.

## Setup

```bash
cd devvit
npm install
npx devvit login            # opens a browser; use the Reddit account that owns the app
npm run dev                 # playtests: creates r/trendpulsedev_dev and installs the app
npx devvit settings set githubToken   # paste a fine-grained PAT with Contents: read/write on the repo
```

The `api.github.com` domain request is submitted for review on first playtest or upload.
Until it is approved, exports fail with a fetch permission error. Terms and privacy
policy links (required for apps that use fetch) are hosted on the dashboard site:
`/terms.html` and `/privacy.html`.
