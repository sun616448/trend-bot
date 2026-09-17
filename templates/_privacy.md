**What is collected.** The Reddit app reads only public post metadata from public subreddits: title, permalink, outbound link, score, comment count, author username, timestamp, flair and up to 600 characters of public self-text. It does not read private messages, votes, saved items, subscriptions, or any non-public data, and it does not track the people who install or view it.

**Where it goes.** Once a week the app writes that public metadata as one JSON file into the public GitHub repository for this project, where a scheduled job combines it with other public sources to build this dashboard.

**Dashboard visitors.** This site is static and sets no cookies. GitHub Pages may log requests per GitHub's own privacy policy.

**Retention.** Weekly export files stay in the repository history so past digests remain viewable.

**Removal.** To have a post excluded, open an issue on the repository with the permalink.
