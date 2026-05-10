// api/like.js — Vercel serverless function (Node.js)
// Handles POST /api/like from the browser.
// GITHUB_TOKEN and GITHUB_REPO live in Vercel env vars only — never in HTML.

const https = require("https");

const GH_TOKEN = process.env.GITHUB_TOKEN || "";
const GH_REPO  = process.env.GITHUB_REPO  || "";
const FILE     = "likes.json";
const BRANCH   = "main";

// Explicitly build the path — no URL parsing, no missing protocol
const API_HOSTNAME = "api.github.com";
const API_PATH     = `/repos/${GH_REPO}/contents/${FILE}`;

const GH_HEADERS = {
  Authorization:          `token ${GH_TOKEN}`,
  Accept:                 "application/vnd.github+json",
  "X-GitHub-Api-Version": "2022-11-28",
  "User-Agent":           "curiosity-digest-likes",
  "Content-Type":         "application/json",
};

// ── Tiny promise wrapper around https ────────────────────────────────────────

function request(method, extraHeaders, body) {
  return new Promise((resolve, reject) => {
    const options = {
      hostname: API_HOSTNAME,
      path:     API_PATH,
      method,
      headers:  { ...GH_HEADERS, ...extraHeaders },
    };
    const req = https.request(options, (res) => {
      let data = "";
      res.on("data", (c) => (data += c));
      res.on("end", () => {
        try { resolve({ status: res.statusCode, body: JSON.parse(data) }); }
        catch { resolve({ status: res.statusCode, body: data }); }
      });
    });
    req.on("error", reject);
    if (body) req.write(body);
    req.end();
  });
}

// ── Read current likes.json ───────────────────────────────────────────────────

async function getLikes() {
  const res = await request("GET", {});
  if (res.status === 404) return { likes: {}, sha: null };
  if (res.status !== 200) throw new Error(`GitHub GET ${res.status}: ${JSON.stringify(res.body)}`);
  const likes = JSON.parse(Buffer.from(res.body.content, "base64").toString());
  return { likes, sha: res.body.sha };
}

// ── Write updated likes.json ──────────────────────────────────────────────────

async function putLikes(likes, sha, action, id) {
  const content = Buffer.from(JSON.stringify(likes, null, 2)).toString("base64");
  const payload = JSON.stringify({
    message: `likes: ${action} ${id}`,
    content,
    branch: BRANCH,
    ...(sha ? { sha } : {}),
  });
  const res = await request("PUT", { "Content-Length": Buffer.byteLength(payload) }, payload);
  if (res.status !== 200 && res.status !== 201)
    throw new Error(`GitHub PUT ${res.status}: ${JSON.stringify(res.body)}`);
  return res.body;
}

// ── Handler ───────────────────────────────────────────────────────────────────

module.exports = async function handler(req, res) {
  res.setHeader("Access-Control-Allow-Origin",  "*");
  res.setHeader("Access-Control-Allow-Methods", "POST, OPTIONS");
  res.setHeader("Access-Control-Allow-Headers", "Content-Type");

  if (req.method === "OPTIONS") return res.status(200).end();
  if (req.method !== "POST")   return res.status(405).json({ error: "POST only" });

  if (!GH_TOKEN || !GH_REPO)
    return res.status(500).json({ error: "Server not configured — check Vercel env vars" });

  const body   = req.body || {};
  const action = body.action || "like";
  const id     = body.id || "";

  if (!id) return res.status(400).json({ error: "missing id" });

  try {
    const { likes, sha } = await getLikes();

    if (action === "unlike") {
      delete likes[id];
    } else {
      likes[id] = {
        id,
        title:   body.title   || "",
        source:  body.source  || "",
        date:    body.date    || "",
        cat:     body.cat     || "",
        link:    body.link    || "",
        summary: body.summary || "",
        likedAt: new Date().toISOString(),
      };
    }

    await putLikes(likes, sha, action, id);
    return res.status(200).json({ ok: true, total: Object.keys(likes).length });

  } catch (err) {
    console.error(err);
    return res.status(500).json({ error: err.message });
  }
};
