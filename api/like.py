"""
api/like.py  —  Vercel serverless function
Handles POST (like/unlike) requests from the browser.
The GitHub PAT lives only in Vercel's environment variables.
Never touches the client.
"""

import json
import os
import base64
from http.server import BaseHTTPRequestHandler


GITHUB_TOKEN = os.environ.get("GITHUB_TOKEN", "")
GITHUB_REPO  = os.environ.get("GITHUB_REPO", "")   # e.g. "ailtotanvir/curiosity-digest"
LIKES_PATH   = "likes.json"
BRANCH       = "main"
API_BASE     = f"https://api.github.com/repos/{GITHUB_REPO}/contents/{LIKES_PATH}"

HEADERS = {
    "Authorization": f"token {GITHUB_TOKEN}",
    "Accept":        "application/vnd.github+json",
    "X-GitHub-Api-Version": "2022-11-28",
    "Content-Type":  "application/json",
}


def gh_get():
    """Fetch current likes.json from GitHub. Returns (data_dict, sha)."""
    import urllib.request
    req = urllib.request.Request(API_BASE, headers=HEADERS)
    try:
        with urllib.request.urlopen(req) as r:
            body = json.loads(r.read())
            content = json.loads(base64.b64decode(body["content"]).decode())
            return content, body["sha"]
    except Exception as e:
        # File doesn't exist yet
        return {}, None


def gh_put(likes: dict, sha: str | None, action: str, post_id: str):
    """Write updated likes.json back to GitHub."""
    import urllib.request
    encoded = base64.b64encode(
        json.dumps(likes, indent=2, ensure_ascii=False).encode()
    ).decode()

    payload = {
        "message": f"likes: {action} {post_id}",
        "content": encoded,
        "branch":  BRANCH,
    }
    if sha:
        payload["sha"] = sha

    data = json.dumps(payload).encode()
    req  = urllib.request.Request(API_BASE, data=data, headers=HEADERS, method="PUT")
    with urllib.request.urlopen(req) as r:
        return json.loads(r.read())


class handler(BaseHTTPRequestHandler):

    def do_OPTIONS(self):
        """CORS preflight."""
        self.send_response(200)
        self._cors()
        self.end_headers()

    def do_POST(self):
        length = int(self.headers.get("Content-Length", 0))
        body   = json.loads(self.rfile.read(length))

        action  = body.get("action", "like")   # "like" or "unlike"
        post_id = body.get("id", "")

        if not post_id:
            self._respond(400, {"error": "missing id"})
            return

        if not GITHUB_TOKEN or not GITHUB_REPO:
            self._respond(500, {"error": "server not configured"})
            return

        try:
            likes, sha = gh_get()

            if action == "unlike":
                likes.pop(post_id, None)
            else:
                from datetime import datetime, timezone
                likes[post_id] = {
                    "id":      post_id,
                    "title":   body.get("title", ""),
                    "source":  body.get("source", ""),
                    "date":    body.get("date", ""),
                    "cat":     body.get("cat", ""),
                    "link":    body.get("link", ""),
                    "summary": body.get("summary", ""),
                    "likedAt": datetime.now(timezone.utc).isoformat(),
                }

            gh_put(likes, sha, action, post_id)
            self._respond(200, {"ok": True, "total": len(likes)})

        except Exception as e:
            self._respond(500, {"error": str(e)})

    def _cors(self):
        self.send_header("Access-Control-Allow-Origin",  "*")
        self.send_header("Access-Control-Allow-Methods", "POST, OPTIONS")
        self.send_header("Access-Control-Allow-Headers", "Content-Type")

    def _respond(self, status: int, data: dict):
        body = json.dumps(data).encode()
        self.send_response(status)
        self._cors()
        self.send_header("Content-Type",   "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def log_message(self, *_):
        pass   # suppress default access log noise
