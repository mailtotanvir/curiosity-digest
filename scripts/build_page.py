"""
Weekly Science Digest Builder
Fetches public RSS/Atom feeds only — no scraping, no cookies, no Meta.
YouTube RSS feeds are official and never blocked.
"""

import feedparser
import re
import json
from datetime import datetime, timedelta, timezone
from dateutil import parser as dparse
from jinja2 import Template
from pathlib import Path

# ── Feed sources ──────────────────────────────────────────────────────────────
# All YouTube channel RSS feeds are official Google-served Atom feeds.
# They never block GitHub Actions IPs. Same for Quanta / New Scientist / drorbn.
#
# Instagram / Facebook removed entirely — Meta blocks GitHub data-center ASNs.
# lookingbackintime has no YouTube channel; substituted with NASA's official feed.

YT = "https://www.youtube.com/feeds/videos.xml?channel_id="

FEEDS = {
    # ── Written / article sources ──────────────────────────────────────────
    "Quanta Magazine":    "https://www.quantamagazine.org/feed/",
    "New Scientist":      "https://www.newscientist.com/feed/home/",
    "Dror Bar-Natan":     "https://drorbn.net/feed",
    "NASA News":          "https://www.nasa.gov/feed/",

    # ── YouTube: Math & Physics ────────────────────────────────────────────
    "3Blue1Brown":        YT + "UCYO_jab_esuFRV4b17AJtAw",
    "Veritasium":         YT + "UCHnyfMqiRRG1u-2MsSQLbXA",
    "MinutePhysics":      YT + "UCUHW94eEFW7hkUMVaZz4eDg",
    "Numberphile":        YT + "UCoxcjq-8xIDTYp3uz647V5A",
    "Stand-up Maths":     YT + "UCSju5G2aFaWMqn-_0YBtq5A",
    "Kurzgesagt":         YT + "UCsXVk37bltHxD1rDPwtNM8Q",
    "Fermilab":           YT + "UCr_M7kA6GBmn8jAYgGZ55fg",

    # ── YouTube: Technology & Explainers ──────────────────────────────────
    "Cleo Abram":         YT + "UC415bOPUcGSamy543abLmRA",

    # ── YouTube: Experiments & Nature ─────────────────────────────────────
    "The Action Lab":     YT + "UC1VLQPn9cYSqx8plbk9RxxQ",
    "Sick Science!":      YT + "UCDom90xOqP4avehFjSJO6NA",   # Steve Spangler
    "Nat. History Museum":YT + "UC7zosc8-0T6Dfyo1bg0w7KA",   # NHM London
}

# ── Time window ───────────────────────────────────────────────────────────────
SINCE = datetime.now(timezone.utc) - timedelta(days=7)

# ── Category allowlist (method 2 — checked first) ─────────────────────────────
GOOD_CATS = {
    "mathematics", "math", "physics", "quantum physics", "quantum mechanics",
    "astronomy", "astrophysics", "space", "cosmology", "relativity",
    "biology", "evolution", "neuroscience", "chemistry", "science",
    "research", "research news", "theoretical physics", "technology",
    "engineering", "artificial intelligence", "computer science",
    "natural history", "nature", "ecology", "stem", "education",
}

# ── Keyword regex (method 1 — regex fallback when no categories) ──────────────
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

# ── Source → category mapping for YouTube (no <category> tags in YT feeds) ───
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
    "Quanta Magazine":     None,   # has real category tags
    "New Scientist":       None,   # has real category tags
    "Dror Bar-Natan":      None,
}

# ── Helpers ───────────────────────────────────────────────────────────────────

def get_categories(entry):
    cats = []
    for tag in entry.get("tags", []):
        term = tag.get("term", "").lower().strip()
        if term:
            cats.append(term)
    return cats


def clean_html(text):
    return re.sub(r'<[^>]+>', '', text or '').strip()


def parse_date(entry):
    for field in ("published", "updated"):
        raw = entry.get(field, "")
        if raw:
            try:
                return dparse.parse(raw)
            except Exception:
                pass
    return None

# ── Main fetch & filter loop ──────────────────────────────────────────────────

kept, rejected = [], []

for source_name, url in FEEDS.items():
    print(f"  Fetching {source_name}…", flush=True)
    feed = feedparser.parse(url)

    if feed.bozo and not feed.entries:
        print(f"    ⚠  parse error, skipping")
        continue

    print(f"    → {len(feed.entries)} entries found")

    for entry in feed.entries[:30]:
        pub = parse_date(entry)
        if pub is None:
            continue

        # Make offset-aware for comparison
        if pub.tzinfo is None:
            pub = pub.replace(tzinfo=timezone.utc)
        if pub < SINCE:
            continue

        title   = clean_html(entry.get("title", ""))
        summary = clean_html(entry.get("summary", entry.get("description", "")))
        link    = entry.get("link", "#")
        text    = f"{title} {summary}"

        # Assign category
        forced_cat = SOURCE_CATEGORY.get(source_name)
        feed_cats  = get_categories(entry)

        if forced_cat:
            # YouTube sources: always trust the source mapping
            keep   = True
            reason = f"trusted source ({forced_cat})"
            cat    = forced_cat
        elif feed_cats and any(c in GOOD_CATS for c in feed_cats):
            # Article source with good category tag
            matched = [c for c in feed_cats if c in GOOD_CATS][0]
            keep   = True
            reason = f"category: {matched}"
            cat    = matched.title()
        elif BLOCK_RE.search(text):
            keep   = False
            reason = "blocked keyword"
            cat    = "—"
        elif KEEP_RE.search(text):
            keep   = True
            reason = "keyword match"
            cat    = "Science"
        else:
            keep   = False
            reason = "no match"
            cat    = "—"

        item = {
            "source":     source_name,
            "title":      title,
            "link":       link,
            "category":   cat,
            "date":       pub.strftime("%Y-%m-%d"),
            "date_str":   pub.strftime("%b %d"),
            "summary":    summary[:220] + ("…" if len(summary) > 220 else ""),
            "feed_cats":  ", ".join(feed_cats),
            "reason":     reason,
        }
        (kept if keep else rejected).append(item)

kept     = sorted(kept,     key=lambda x: x["date"], reverse=True)
rejected = sorted(rejected, key=lambda x: x["date"], reverse=True)
print(f"\n✓ {len(kept)} kept  |  {len(rejected)} filtered")

# ── Templates ─────────────────────────────────────────────────────────────────

INDEX_HTML = """<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>Weekly Curiosity Digest</title>
  <style>
    :root {
      --bg: #f8f9fa; --surface: #fff; --border: #e5e7eb;
      --accent: #0a58ca; --muted: #6b7280; --tag-bg: #eff6ff;
      --tag-color: #1d4ed8; --heading: #111827;
    }
    @media (prefers-color-scheme: dark) {
      :root {
        --bg: #0f172a; --surface: #1e293b; --border: #334155;
        --accent: #60a5fa; --muted: #94a3b8; --tag-bg: #1e3a5f;
        --tag-color: #93c5fd; --heading: #f1f5f9;
      }
    }
    *, *::before, *::after { box-sizing: border-box; margin: 0; padding: 0; }
    body {
      font-family: system-ui, -apple-system, sans-serif;
      background: var(--bg); color: var(--heading);
      max-width: 820px; margin: 0 auto; padding: 2rem 1.25rem 4rem;
      line-height: 1.6;
    }
    header { margin-bottom: 2rem; }
    h1 { font-size: 1.75rem; font-weight: 800; margin-bottom: .3rem; }
    .meta { color: var(--muted); font-size: .875rem; }
    .meta a { color: var(--accent); text-decoration: none; }
    .meta a:hover { text-decoration: underline; }

    /* Filter tabs */
    .filters {
      display: flex; flex-wrap: wrap; gap: .4rem;
      margin: 1.5rem 0;
    }
    .filter-btn {
      background: var(--surface); border: 1px solid var(--border);
      color: var(--muted); border-radius: 999px;
      padding: .3rem .85rem; font-size: .8rem; cursor: pointer;
      transition: all .15s;
    }
    .filter-btn:hover, .filter-btn.active {
      border-color: var(--accent); color: var(--accent);
      background: var(--tag-bg);
    }

    /* Cards */
    .card {
      background: var(--surface); border: 1px solid var(--border);
      border-radius: 10px; padding: 1.1rem 1.25rem;
      margin-bottom: .85rem; transition: border-color .15s;
    }
    .card:hover { border-color: var(--accent); }
    .card-meta {
      display: flex; align-items: center; gap: .5rem;
      font-size: .78rem; color: var(--muted); margin-bottom: .4rem;
      flex-wrap: wrap;
    }
    .tag {
      background: var(--tag-bg); color: var(--tag-color);
      border-radius: 4px; padding: 1px 7px; font-size: .72rem;
      font-weight: 500;
    }
    .card h3 { font-size: 1rem; font-weight: 600; margin-bottom: .35rem; }
    .card h3 a { color: var(--heading); text-decoration: none; }
    .card h3 a:hover { color: var(--accent); }
    .card p { font-size: .875rem; color: var(--muted); }

    .empty { text-align: center; color: var(--muted); padding: 3rem 0; }
    footer {
      margin-top: 3rem; padding-top: 1rem;
      border-top: 1px solid var(--border);
      font-size: .78rem; color: var(--muted); text-align: center;
    }
  </style>
</head>
<body>
<header>
  <h1>🧠 Weekly Curiosity Digest</h1>
  <p class="meta">
    Updated {{ now }} &nbsp;·&nbsp;
    {{ kept|length }} posts kept &nbsp;·&nbsp;
    <a href="rejected.html">{{ rej|length }} filtered out →</a>
  </p>
</header>

<div class="filters" id="filters">
  <button class="filter-btn active" data-cat="all">All</button>
  {% for cat in categories %}
  <button class="filter-btn" data-cat="{{ cat }}">{{ cat }}</button>
  {% endfor %}
</div>

<div id="cards">
{% if kept %}
  {% for it in kept %}
  <div class="card" data-cat="{{ it.category }}">
    <div class="card-meta">
      <span>{{ it.source }}</span>
      <span>·</span>
      <span>{{ it.date_str }}</span>
      <span class="tag">{{ it.category }}</span>
      <span class="tag" style="opacity:.65">{{ it.reason }}</span>
    </div>
    <h3><a href="{{ it.link }}" target="_blank" rel="noopener">{{ it.title }}</a></h3>
    {% if it.summary %}<p>{{ it.summary }}</p>{% endif %}
  </div>
  {% endfor %}
{% else %}
  <div class="empty">No science posts found this week. Check rejected.html for clues.</div>
{% endif %}
</div>

<footer>Generated by GitHub Actions every Saturday · Sources: YouTube RSS &amp; public feeds · No scraping</footer>

<script>
  const btns  = document.querySelectorAll('.filter-btn');
  const cards = document.querySelectorAll('.card');
  btns.forEach(btn => {
    btn.addEventListener('click', () => {
      btns.forEach(b => b.classList.remove('active'));
      btn.classList.add('active');
      const cat = btn.dataset.cat;
      cards.forEach(c => {
        c.style.display = (cat === 'all' || c.dataset.cat === cat) ? '' : 'none';
      });
    });
  });
</script>
</body>
</html>"""


REJECTED_HTML = """<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>Filtered posts — Curiosity Digest</title>
  <style>
    body { font-family: system-ui,sans-serif; max-width:820px; margin:40px auto;
           padding:0 1.25rem 4rem; color:#111; line-height:1.6; }
    @media (prefers-color-scheme:dark) { body { background:#0f172a; color:#f1f5f9; } a{color:#60a5fa;} }
    h1 { margin-bottom:.3rem; }
    .back { font-size:.875rem; margin-bottom:2rem; display:block; }
    li { margin-bottom:1rem; }
    .reason { color:#9ca3af; font-size:.8rem; margin-left:.4rem; }
    small { color:#6b7280; }
  </style>
</head>
<body>
  <h1>🗑 Filtered posts this week</h1>
  <a class="back" href="index.html">← Back to digest</a>
  <p style="margin-bottom:1.5rem;color:#6b7280">
    {{ rej|length }} posts were filtered. Use this page to tune your keywords.
  </p>
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

categories = sorted(set(it["category"] for it in kept if it["category"] != "—"))
now        = datetime.now(timezone.utc).strftime("%B %d, %Y at %H:%M UTC")

Path("index.html").write_text(
    Template(INDEX_HTML).render(kept=kept, rej=rejected, now=now, categories=categories),
    encoding="utf-8"
)
Path("rejected.html").write_text(
    Template(REJECTED_HTML).render(rej=rejected),
    encoding="utf-8"
)
Path("debug.json").write_text(
    json.dumps({"kept": kept, "rejected": rejected}, indent=2, default=str),
    encoding="utf-8"
)

print("✅  Written → index.html  rejected.html  debug.json")
