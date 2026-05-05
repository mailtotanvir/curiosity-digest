"""
Curiosity Digest Builder
Fetches public RSS/Atom feeds only — no scraping, no cookies, no Meta.
YouTube RSS feeds are official and never blocked.

Likes are stored in likes.json in the repo via GitHub API.
They sync across all browsers and devices automatically.
"""

import feedparser
import re
import json
from datetime import datetime, timedelta, timezone
from dateutil import parser as dparse
from jinja2 import Environment
from pathlib import Path

# ── Feed sources ──────────────────────────────────────────────────────────────
YT = "https://www.youtube.com/feeds/videos.xml?channel_id="

FEEDS = {
    "Quanta Magazine":     "https://www.quantamagazine.org/feed/",
    "New Scientist":       "https://www.newscientist.com/feed/home/",
    "Dror Bar-Natan":      "https://drorbn.net/feed",
    "NASA News":           "https://www.nasa.gov/feed/",
    "3Blue1Brown":         YT + "UCYO_jab_esuFRV4b17AJtAw",
    "Veritasium":          YT + "UCHnyfMqiRRG1u-2MsSQLbXA",
    "MinutePhysics":       YT + "UCUHW94eEFW7hkUMVaZz4eDg",
    "Numberphile":         YT + "UCoxcjq-8xIDTYp3uz647V5A",
    "Stand-up Maths":      YT + "UCSju5G2aFaWMqn-_0YBtq5A",
    "Kurzgesagt":          YT + "UCsXVk37bltHxD1rDPwtNM8Q",
    "Fermilab":            YT + "UCr_M7kA6GBmn8jAYgGZ55fg",
    "Cleo Abram":          YT + "UC415bOPUcGSamy543abLmRA",
    "The Action Lab":      YT + "UC1VLQPn9cYSqx8plbk9RxxQ",
    "Sick Science!":       YT + "UCDom90xOqP4avehFjSJO6NA",
    "Nat. History Museum": YT + "UC7zosc8-0T6Dfyo1bg0w7KA",
}

SINCE = datetime.now(timezone.utc) - timedelta(days=7)

GOOD_CATS = {
    "mathematics","math","physics","quantum physics","quantum mechanics",
    "astronomy","astrophysics","space","cosmology","relativity",
    "biology","evolution","neuroscience","chemistry","science",
    "research","research news","theoretical physics","technology",
    "engineering","artificial intelligence","computer science",
    "natural history","nature","ecology","stem","education",
}

KEEP_RE = re.compile(
    r'\b(physic|quantum|relativ|astronom|cosmo|galax|nebula|neutrino|'
    r'black\s*hole|dark\s*matter|dark\s*energy|higgs|particle|'
    r'math|topolog|knot|fourier|proof|theorem|equat|algebr|geometr|calculus|'
    r'biolog|dna|rna|crispr|evolut|neuron|synapse|protein|'
    r'chemist|molecule|reaction|compound|element|'
    r'experiment|hypothesis|research|discovery|scientist|'
    r'robot|ai\b|machine\s*learn|neural\s*net|algorithm|'
    r'climate|atmosphere|geology|fossil|dinosaur|species)\b',
    re.I
)
BLOCK_RE = re.compile(
    r'\b(election|politic|trump|biden|harris|congress|senate|democrat|republican|'
    r'nba|nfl|nhl|mlb|football|soccer|basketball|baseball|cricket\s*score|'
    r'celebrity|kardashian|taylor\s*swift|beyonc|oscar|grammy|'
    r'movie\s*review|box\s*office|album|playlist|gaming|esport|'
    r'stock|crypto|bitcoin|ethereum|invest|financ)\b',
    re.I
)

SOURCE_CATEGORY = {
    "3Blue1Brown":         "Mathematics",
    "Numberphile":         "Mathematics",
    "Stand-up Maths":      "Mathematics",
    "Veritasium":          "Physics",
    "MinutePhysics":       "Physics",
    "Fermilab":            "Physics",
    "Kurzgesagt":          "Science",
    "The Action Lab":      "Experiments",
    "Sick Science!":       "Experiments",
    "Cleo Abram":          "Technology",
    "Nat. History Museum": "Nature",
    "NASA News":           "Astronomy",
    "Quanta Magazine":     None,
    "New Scientist":       None,
    "Dror Bar-Natan":      None,
}

# ── Helpers ───────────────────────────────────────────────────────────────────

def get_categories(entry):
    return [t.get("term","").lower().strip()
            for t in entry.get("tags",[]) if t.get("term","").strip()]

def clean_html(text):
    return re.sub(r'<[^>]+>', '', text or '').strip()

def parse_date(entry):
    for field in ("published", "updated"):
        raw = entry.get(field, "")
        if raw:
            try: return dparse.parse(raw)
            except: pass
    return None

def make_id(link):
    import hashlib
    return hashlib.md5(link.encode()).hexdigest()[:12]

# ── Fetch & filter ────────────────────────────────────────────────────────────

kept, rejected = [], []

for source_name, url in FEEDS.items():
    print(f"  Fetching {source_name}…", flush=True)
    feed = feedparser.parse(url)
    if feed.bozo and not feed.entries:
        print(f"    ⚠  parse error, skipping"); continue
    print(f"    → {len(feed.entries)} entries")

    for entry in feed.entries[:30]:
        pub = parse_date(entry)
        if pub is None: continue
        if pub.tzinfo is None: pub = pub.replace(tzinfo=timezone.utc)
        if pub < SINCE: continue

        title   = clean_html(entry.get("title", ""))
        summary = clean_html(entry.get("summary", entry.get("description", "")))
        link    = entry.get("link", "#")
        text    = f"{title} {summary}"
        cats    = get_categories(entry)
        forced  = SOURCE_CATEGORY.get(source_name)

        if forced:
            keep, reason, cat = True, f"trusted source ({forced})", forced
        elif cats and any(c in GOOD_CATS for c in cats):
            matched = next(c for c in cats if c in GOOD_CATS)
            keep, reason, cat = True, f"category: {matched}", matched.title()
        elif BLOCK_RE.search(text):
            keep, reason, cat = False, "blocked keyword", "—"
        elif KEEP_RE.search(text):
            keep, reason, cat = True, "keyword match", "Science"
        else:
            keep, reason, cat = False, "no match", "—"

        item = {
            "id":        make_id(link),
            "source":    source_name,
            "title":     title,
            "link":      link,
            "category":  cat,
            "date":      pub.strftime("%Y-%m-%d"),
            "date_str":  pub.strftime("%b %d"),
            "summary":   summary[:220] + ("…" if len(summary) > 220 else ""),
            "feed_cats": ", ".join(cats),
            "reason":    reason,
        }
        (kept if keep else rejected).append(item)

kept     = sorted(kept,     key=lambda x: x["date"], reverse=True)
rejected = sorted(rejected, key=lambda x: x["date"], reverse=True)
print(f"\n✓ {len(kept)} kept  |  {len(rejected)} filtered")

# ── HTML template ─────────────────────────────────────────────────────────────
# The JS in the page:
#   1. On load  — fetches likes.json from the repo via GitHub raw URL (public, no auth)
#   2. On like  — calls GitHub Contents API to read+update likes.json (needs GH_PAT)
#   3. GH_PAT is injected into the page at build time from the GITHUB_TOKEN env var.
#      It has ONLY contents:write on this one repo. It is NOT the Actions secret itself —
#      the Actions workflow writes it into the HTML during build so the page can call
#      the GitHub API from the browser. Scope it to the minimum (fine-grained PAT,
#      contents read+write on this repo only).

INDEX_HTML = r"""<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>Curiosity Digest</title>
  <style>
    :root {
      --bg:#f8f9fa; --surface:#fff; --border:#e5e7eb;
      --accent:#0a58ca; --muted:#6b7280;
      --tag-bg:#eff6ff; --tag-color:#1d4ed8; --heading:#111827;
      --like-off:#d1d5db; --like-on:#ef4444;
    }
    @media (prefers-color-scheme:dark) { :root {
      --bg:#0f172a; --surface:#1e293b; --border:#334155;
      --accent:#60a5fa; --muted:#94a3b8;
      --tag-bg:#1e3a5f; --tag-color:#93c5fd; --heading:#f1f5f9;
      --like-off:#475569; --like-on:#f87171;
    }}
    *,*::before,*::after { box-sizing:border-box; margin:0; padding:0 }
    body { font-family:system-ui,-apple-system,sans-serif; background:var(--bg);
           color:var(--heading); max-width:820px; margin:0 auto;
           padding:2rem 1.25rem 4rem; line-height:1.6 }
    header { margin-bottom:1.75rem }
    h1 { font-size:1.75rem; font-weight:800; margin-bottom:.3rem }
    .meta { color:var(--muted); font-size:.875rem }
    .meta a { color:var(--accent); text-decoration:none }
    .meta a:hover { text-decoration:underline }

    .tabs { display:flex; flex-wrap:wrap; gap:.4rem; margin:1.25rem 0 1.5rem }
    .tab-btn { background:var(--surface); border:1px solid var(--border);
               color:var(--muted); border-radius:999px; padding:.3rem .85rem;
               font-size:.8rem; cursor:pointer; transition:all .15s;
               display:flex; align-items:center; gap:.35rem }
    .tab-btn:hover,.tab-btn.active { border-color:var(--accent);
               color:var(--accent); background:var(--tag-bg) }
    .badge { background:var(--like-on); color:#fff; border-radius:999px;
             padding:0 6px; font-size:.7rem; font-weight:700;
             display:none; line-height:1.6 }
    .badge.visible { display:inline }

    .card { position:relative; background:var(--surface);
            border:1px solid var(--border); border-radius:10px;
            padding:1.1rem 1.25rem 1.1rem 3rem;
            margin-bottom:.85rem; transition:border-color .15s }
    .card:hover { border-color:var(--accent) }
    .card-meta { display:flex; align-items:center; gap:.5rem;
                 font-size:.78rem; color:var(--muted);
                 margin-bottom:.4rem; flex-wrap:wrap }
    .tag { background:var(--tag-bg); color:var(--tag-color);
           border-radius:4px; padding:1px 7px;
           font-size:.72rem; font-weight:500 }
    .card h3 { font-size:1rem; font-weight:600; margin-bottom:.35rem }
    .card h3 a { color:var(--heading); text-decoration:none }
    .card h3 a:hover { color:var(--accent) }
    .card p { font-size:.875rem; color:var(--muted) }

    .like-btn { position:absolute; left:.9rem; top:1.05rem;
                background:none; border:none; cursor:pointer;
                font-size:1.3rem; line-height:1; padding:2px;
                color:var(--like-off); transition:color .15s,transform .15s }
    .like-btn:hover { transform:scale(1.25) }
    .like-btn.liked { color:var(--like-on) }
    .like-btn.saving { opacity:.5; pointer-events:none }
    .like-btn.pop { animation:pop .25s ease }
    @keyframes pop { 0%{transform:scale(1)} 50%{transform:scale(1.5)} 100%{transform:scale(1)} }

    #liked-view { display:none }
    #liked-view.active { display:block }
    #feed-view.hidden { display:none }
    .liked-header { font-size:.875rem; color:var(--muted); margin-bottom:1.25rem }
    .liked-empty { text-align:center; color:var(--muted); padding:3rem 0 }
    .unlike-hint { font-size:.72rem; color:var(--muted); margin-top:.25rem; opacity:.7 }
    .sync-status { font-size:.75rem; color:var(--muted); margin-left:.5rem; opacity:.8 }

    .empty { text-align:center; color:var(--muted); padding:3rem 0 }
    footer { margin-top:3rem; padding-top:1rem; border-top:1px solid var(--border);
             font-size:.78rem; color:var(--muted); text-align:center }
  </style>
</head>
<body>

<header>
  <h1>🔭 Curiosity Digest</h1>
  <p class="meta">
    Updated {{ now }} &nbsp;·&nbsp;
    {{ kept|length }} posts &nbsp;·&nbsp;
    <a href="rejected.html">{{ rej|length }} filtered →</a>
    <span class="sync-status" id="sync-status"></span>
  </p>
</header>

<div class="tabs">
  <button class="tab-btn active" data-cat="all">All</button>
  {% for cat in categories %}
  <button class="tab-btn" data-cat="{{ cat }}">{{ cat }}</button>
  {% endfor %}
  <button class="tab-btn" id="liked-tab">
    ♥ Liked <span class="badge" id="like-badge"></span>
  </button>
</div>

<div id="feed-view">
{% if kept %}
  {% for it in kept %}
  <div class="card"
       data-id="{{ it.id }}"
       data-cat="{{ it.category }}"
       data-title="{{ it.title }}"
       data-source="{{ it.source }}"
       data-date="{{ it.date_str }}"
       data-cat-label="{{ it.category }}"
       data-link="{{ it.link }}"
       data-summary="{{ it.summary }}">
    <button class="like-btn" aria-label="Like" title="Like this post">♥</button>
    <div class="card-meta">
      <span>{{ it.source }}</span> · <span>{{ it.date_str }}</span>
      <span class="tag">{{ it.category }}</span>
      <span class="tag" style="opacity:.6">{{ it.reason }}</span>
    </div>
    <h3><a href="{{ it.link }}" target="_blank" rel="noopener">{{ it.title }}</a></h3>
    {% if it.summary %}<p>{{ it.summary }}</p>{% endif %}
  </div>
  {% endfor %}
{% else %}
  <div class="empty">No posts found this week.</div>
{% endif %}
</div>

<div id="liked-view">
  <p class="liked-header">
    Posts saved across all weekly digests — synced to your repo.
    <a href="likes.json" target="_blank" style="color:var(--accent);text-decoration:none;font-size:.8rem">
      Download likes.json →
    </a>
  </p>
  <div id="liked-cards"></div>
</div>

<footer>Curiosity Digest · GitHub Actions · YouTube RSS &amp; public feeds · Likes saved to repo</footer>

<script>
  // ── Config (injected at build time by GitHub Actions) ────────────────────
  // GH_PAT: fine-grained PAT, contents read+write on THIS REPO ONLY.
  // It is embedded in the built HTML. Use a minimal-scope token.
  const GH_PAT  = "{{ gh_pat }}";
  const GH_REPO = "{{ gh_repo }}";   // e.g. "ailtotanvir/brain-food"
  const LIKES_PATH = "likes.json";

  // ── GitHub API helpers ───────────────────────────────────────────────────
  const RAW_URL   = `https://raw.githubusercontent.com/${GH_REPO}/main/${LIKES_PATH}`;
  const API_URL   = `https://api.github.com/repos/${GH_REPO}/contents/${LIKES_PATH}`;
  const API_HEADS = {
    "Authorization": `token ${GH_PAT}`,
    "Accept":        "application/vnd.github+json",
    "X-GitHub-Api-Version": "2022-11-28",
  };

  let currentSha = null;   // needed for update calls

  function setStatus(msg) {
    document.getElementById('sync-status').textContent = msg;
  }

  async function loadLikes() {
    // Read from raw CDN — fast, no auth needed
    try {
      const r = await fetch(RAW_URL + "?cb=" + Date.now());
      if (r.status === 404) return {};
      if (!r.ok) throw new Error(r.status);
      return await r.json();
    } catch (e) {
      console.warn("Could not load likes.json:", e);
      return {};
    }
  }

  async function saveLikes(likes) {
    // Must use API (not raw) to get SHA and write back
    const content = btoa(unescape(encodeURIComponent(JSON.stringify(likes, null, 2))));

    // Fetch current SHA if we don't have it
    if (!currentSha) {
      try {
        const r = await fetch(API_URL, { headers: API_HEADS });
        if (r.ok) { const d = await r.json(); currentSha = d.sha; }
      } catch(e) {}
    }

    const body = {
      message: `likes: update ${new Date().toISOString().slice(0,10)}`,
      content,
      ...(currentSha ? { sha: currentSha } : {}),
    };

    const r = await fetch(API_URL, {
      method: "PUT",
      headers: { ...API_HEADS, "Content-Type": "application/json" },
      body: JSON.stringify(body),
    });

    if (!r.ok) throw new Error(`GitHub API ${r.status}: ${await r.text()}`);
    const d = await r.json();
    currentSha = d.content.sha;
  }

  // ── State ────────────────────────────────────────────────────────────────
  let likes = {};

  const badge = document.getElementById('like-badge');
  function refreshBadge() {
    const n = Object.keys(likes).length;
    badge.textContent = n;
    badge.classList.toggle('visible', n > 0);
  }

  // ── Liked panel renderer ─────────────────────────────────────────────────
  function renderLiked() {
    const entries = Object.values(likes)
                          .sort((a,b) => (b.likedAt||0)-(a.likedAt||0));
    const box = document.getElementById('liked-cards');

    if (!entries.length) {
      box.innerHTML = '<div class="liked-empty">No liked posts yet. Hit ♥ on any card.</div>';
      return;
    }

    box.innerHTML = entries.map(p => `
      <div class="card" data-id="${p.id}">
        <button class="like-btn liked" data-id="${p.id}" title="Unlike">♥</button>
        <div class="card-meta">
          <span>${p.source}</span> · <span>${p.date}</span>
          <span class="tag">${p.cat}</span>
          <span class="tag" style="opacity:.55">saved ${new Date(p.likedAt).toLocaleDateString()}</span>
        </div>
        <h3><a href="${p.link}" target="_blank" rel="noopener">${p.title}</a></h3>
        ${p.summary ? `<p>${p.summary}</p>` : ''}
        <p class="unlike-hint">Click ♥ to remove</p>
      </div>`).join('');

    box.querySelectorAll('.like-btn').forEach(btn => {
      btn.addEventListener('click', async () => {
        const id = btn.dataset.id;
        delete likes[id];
        btn.classList.add('saving');
        setStatus('saving…');
        try {
          await saveLikes(likes);
          setStatus('saved ✓');
        } catch(e) {
          setStatus('save failed — check console');
          console.error(e);
        }
        refreshBadge();
        renderLiked();
        const feedBtn = document.querySelector(`#feed-view [data-id="${id}"] .like-btn`);
        if (feedBtn) feedBtn.classList.remove('liked');
        setTimeout(() => setStatus(''), 2000);
      });
    });
  }

  // ── Wire feed card hearts ────────────────────────────────────────────────
  document.querySelectorAll('#feed-view .card').forEach(card => {
    const id  = card.dataset.id;
    const btn = card.querySelector('.like-btn');
    if (!btn) return;

    btn.addEventListener('click', async () => {
      const wasLiked = !!likes[id];
      if (wasLiked) {
        delete likes[id];
      } else {
        likes[id] = {
          id,
          title:   card.dataset.title,
          source:  card.dataset.source,
          date:    card.dataset.date,
          cat:     card.dataset.catLabel,
          link:    card.dataset.link,
          summary: card.dataset.summary,
          likedAt: Date.now(),
        };
      }

      btn.classList.toggle('liked', !wasLiked);
      btn.classList.add('pop', 'saving');
      btn.addEventListener('animationend', () => btn.classList.remove('pop'), {once:true});
      refreshBadge();
      setStatus('saving…');

      try {
        await saveLikes(likes);
        setStatus('saved ✓');
      } catch(e) {
        // Roll back on failure
        if (wasLiked) likes[id] = {};
        else delete likes[id];
        btn.classList.toggle('liked', wasLiked);
        refreshBadge();
        setStatus('save failed — check console');
        console.error(e);
      } finally {
        btn.classList.remove('saving');
        setTimeout(() => setStatus(''), 2000);
      }
    });
  });

  // ── Tab switching ────────────────────────────────────────────────────────
  const feedView  = document.getElementById('feed-view');
  const likedView = document.getElementById('liked-view');
  const likedTab  = document.getElementById('liked-tab');
  const tabBtns   = document.querySelectorAll('.tab-btn:not(#liked-tab)');
  const allCards  = document.querySelectorAll('#feed-view .card');

  tabBtns.forEach(btn => {
    btn.addEventListener('click', () => {
      tabBtns.forEach(b => b.classList.remove('active'));
      likedTab.classList.remove('active');
      btn.classList.add('active');
      feedView.classList.remove('hidden');
      likedView.classList.remove('active');
      const cat = btn.dataset.cat;
      allCards.forEach(c => {
        c.style.display = (cat === 'all' || c.dataset.cat === cat) ? '' : 'none';
      });
    });
  });

  likedTab.addEventListener('click', () => {
    tabBtns.forEach(b => b.classList.remove('active'));
    likedTab.classList.add('active');
    feedView.classList.add('hidden');
    likedView.classList.add('active');
    renderLiked();
  });

  // ── Boot: load likes from repo ───────────────────────────────────────────
  (async () => {
    setStatus('loading likes…');
    likes = await loadLikes();
    // Apply liked state to feed cards
    document.querySelectorAll('#feed-view .card').forEach(card => {
      if (likes[card.dataset.id]) {
        card.querySelector('.like-btn')?.classList.add('liked');
      }
    });
    refreshBadge();
    setStatus('');
  })();
</script>
</body>
</html>"""


REJECTED_HTML = """<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>Filtered — Curiosity Digest</title>
  <style>
    body{font-family:system-ui,sans-serif;max-width:820px;margin:40px auto;
         padding:0 1.25rem 4rem;color:#111;line-height:1.6}
    @media(prefers-color-scheme:dark){body{background:#0f172a;color:#f1f5f9}a{color:#60a5fa}}
    h1{margin-bottom:.3rem}
    .back{font-size:.875rem;margin-bottom:2rem;display:block}
    li{margin-bottom:1rem}
    .reason{color:#9ca3af;font-size:.8rem;margin-left:.4rem}
    small{color:#6b7280}
  </style>
</head>
<body>
  <h1>🗑 Filtered this week</h1>
  <a class="back" href="index.html">← Back to digest</a>
  <p style="margin-bottom:1.5rem;color:#6b7280">{{ rej|length }} posts filtered. Use this to tune keywords.</p>
  <ol>
  {% for it in rej %}
    <li>
      <a href="{{ it.link }}" target="_blank">{{ it.title }}</a>
      <span class="reason">[{{ it.reason }}]</span><br>
      <small>{{ it.source }} · {{ it.date_str }}{% if it.feed_cats %} · cats: {{ it.feed_cats }}{% endif %}</small>
    </li>
  {% endfor %}
  </ol>
</body>
</html>"""

# ── Render & write ────────────────────────────────────────────────────────────

import os

categories = sorted(set(it["category"] for it in kept if it["category"] != "—"))
now        = datetime.now(timezone.utc).strftime("%B %d, %Y at %H:%M UTC")

# GH_PAT and GITHUB_REPOSITORY are injected by the Actions workflow.
# Locally they'll be empty strings — likes won't save, but the page still works.
gh_pat  = os.environ.get("GH_PAT", "")
gh_repo = os.environ.get("GITHUB_REPOSITORY", "")

env = Environment(autoescape=True)
Path("index.html").write_text(
    env.from_string(INDEX_HTML).render(
        kept=kept, rej=rejected, now=now,
        categories=categories,
        gh_pat=gh_pat,
        gh_repo=gh_repo,
    ),
    encoding="utf-8"
)
Path("rejected.html").write_text(
    env.from_string(REJECTED_HTML).render(rej=rejected),
    encoding="utf-8"
)
Path("debug.json").write_text(
    json.dumps({"kept": kept, "rejected": rejected}, indent=2, default=str),
    encoding="utf-8"
)

# Create likes.json if it doesn't exist yet (first run)
if not Path("likes.json").exists():
    Path("likes.json").write_text("{}", encoding="utf-8")
    print("  Created empty likes.json")

print("✅  Written → index.html  rejected.html  debug.json  likes.json")
