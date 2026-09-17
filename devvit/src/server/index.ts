import { createServer, getServerPort, reddit, settings } from "@devvit/web/server";
import type { IncomingMessage, ServerResponse } from "node:http";
import { PER_FRONTPAGE, PER_SUBREDDIT, SUBREDDITS } from "./subreddits";

type ExportedPost = {
  subreddit: string;
  id: string;
  title: string;
  permalink: string;
  url: string;
  score: number;
  num_comments: number;
  author: string;
  created_utc: number;
  thumbnail: string | null;
  body: string;
  flair: string | null;
};

function isoWeek(d = new Date()): string {
  const date = new Date(Date.UTC(d.getUTCFullYear(), d.getUTCMonth(), d.getUTCDate()));
  const day = date.getUTCDay() || 7;
  date.setUTCDate(date.getUTCDate() + 4 - day);
  const yearStart = new Date(Date.UTC(date.getUTCFullYear(), 0, 1));
  const week = Math.ceil(((date.getTime() - yearStart.getTime()) / 86400000 + 1) / 7);
  return `${date.getUTCFullYear()}-W${String(week).padStart(2, "0")}`;
}

async function collect(): Promise<{ posts: ExportedPost[]; errors: string[] }> {
  const posts: ExportedPost[] = [];
  const errors: string[] = [];
  for (const sub of SUBREDDITS) {
    const limit = sub === "all" || sub === "popular" ? PER_FRONTPAGE : PER_SUBREDDIT;
    try {
      const listing = reddit.getTopPosts({ subredditName: sub, timeframe: "week", limit, pageSize: limit });
      const items = await listing.all();
      for (const p of items) {
        if (p.nsfw || p.stickied) continue;
        posts.push({
          subreddit: p.subredditName,
          id: p.id,
          title: p.title,
          permalink: `https://www.reddit.com${p.permalink}`,
          url: p.url,
          score: p.score,
          num_comments: p.numberOfComments,
          author: p.authorName ?? "",
          created_utc: Math.floor(p.createdAt.getTime() / 1000),
          thumbnail: p.thumbnail?.url ?? null,
          body: (p.body ?? "").slice(0, 600),
          flair: p.flair?.text ?? null,
        });
      }
    } catch (e) {
      errors.push(`${sub}: ${e instanceof Error ? e.message : String(e)}`);
    }
  }
  return { posts, errors };
}

async function pushToGitHub(week: string, payload: unknown): Promise<string> {
  const token = (await settings.get("githubToken")) as string | undefined;
  const repo = ((await settings.get("githubRepo")) as string | undefined) ?? "sun616448/trend-bot";
  if (!token) throw new Error("githubToken setting is empty; run `npx devvit settings set githubToken`");
  const path = `data/reddit/${week}.json`;
  const api = `https://api.github.com/repos/${repo}/contents/${path}`;
  const headers = {
    Authorization: `Bearer ${token}`,
    Accept: "application/vnd.github+json",
    "X-GitHub-Api-Version": "2022-11-28",
    "Content-Type": "application/json",
    "User-Agent": "trendpulse-reddit-devvit",
  };
  let sha: string | undefined;
  const existing = await fetch(api, { headers });
  if (existing.status === 200) sha = ((await existing.json()) as { sha: string }).sha;
  const content = Buffer.from(JSON.stringify(payload, null, 1)).toString("base64");
  const res = await fetch(api, {
    method: "PUT",
    headers,
    body: JSON.stringify({ message: `reddit: ${week}`, content, ...(sha ? { sha } : {}) }),
  });
  if (res.status !== 200 && res.status !== 201) {
    throw new Error(`GitHub PUT ${path} failed: ${res.status} ${(await res.text()).slice(0, 200)}`);
  }
  return path;
}

async function runExport(): Promise<string> {
  const week = isoWeek();
  const { posts, errors } = await collect();
  const payload = { week, exported_at: new Date().toISOString(), post_count: posts.length, errors, posts };
  const path = await pushToGitHub(week, payload);
  const msg = `Exported ${posts.length} posts to ${path}${errors.length ? ` (${errors.length} subreddit errors)` : ""}`;
  console.log(msg, errors);
  return msg;
}

async function readBody(req: IncomingMessage): Promise<string> {
  return new Promise((resolve) => {
    let data = "";
    req.on("data", (c) => (data += c));
    req.on("end", () => resolve(data));
  });
}

function json(res: ServerResponse, status: number, body: unknown): void {
  res.writeHead(status, { "Content-Type": "application/json" });
  res.end(JSON.stringify(body));
}

const server = createServer(async (req: IncomingMessage, res: ServerResponse) => {
  const url = req.url ?? "";
  try {
    await readBody(req);
    if (req.method === "POST" && url.startsWith("/internal/scheduler/collect-weekly")) {
      await runExport();
      return json(res, 200, { status: "ok" });
    }
    if (req.method === "POST" && url.startsWith("/internal/menu/run-now")) {
      const msg = await runExport();
      return json(res, 200, { showToast: msg });
    }
    return json(res, 404, { error: "not found", status: 404 });
  } catch (err) {
    const msg = err instanceof Error ? err.message : String(err);
    console.error("trendpulse-reddit error:", msg);
    if (url.startsWith("/internal/menu/")) return json(res, 200, { showToast: `Export failed: ${msg.slice(0, 160)}` });
    return json(res, 500, { error: msg, status: 500 });
  }
});

server.on("error", (err) => console.error(`server error; ${err.stack}`));
server.listen(getServerPort());
