#!/usr/bin/env python3
"""
Phase 4, Bite 2: LinkedIn cross-post.

Default: dry run — prints payload + text, no network.
  python3 scripts/post_to_linkedin.py --slug <slug>

With --post: actually posts via /rest/posts.
  LINKEDIN_ACCESS_TOKEN, LINKEDIN_AUTHOR_URN, LINKEDIN_VERSION must be set.
  python3 scripts/post_to_linkedin.py --slug <slug> --post

Reads post frontmatter (title, description, linkedinSummary).
"""

import argparse
import json
import os
import re
import sys
import urllib.error
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
POSTS_DIR = ROOT / "src" / "content" / "posts"

DEFAULT_BASE = "https://danilegend.github.io/blog-supply-chain"
LINKEDIN_API = "https://api.linkedin.com/rest/posts"

FM_RE = re.compile(r'^([A-Za-z_][A-Za-z0-9_]*):\s*"?(.*?)"?\s*$')

# LinkedIn limits
MAX_COMMENTARY = 3000
MAX_TITLE = 200
MAX_DESCRIPTION = 256


# ---------- frontmatter ----------
def parse_frontmatter(text):
    if not text.startswith("---"):
        raise SystemExit("File does not start with ---")
    end = text.find("\n---", 4)
    if end == -1:
        raise SystemExit("File has no closing ---")
    data = {}
    for line in text[4:end].strip().splitlines():
        m = FM_RE.match(line.strip())
        if not m:
            continue
        data[m.group(1)] = m.group(2).replace('\\"', '"')
    return data


def load_post(slug):
    filename = slug if slug.endswith(".md") else f"{slug}.md"
    path = POSTS_DIR / filename
    if not path.exists():
        raise SystemExit(f"Post not found: {path}")
    fm = parse_frontmatter(path.read_text(encoding="utf-8"))
    for key in ("title", "linkedinSummary", "description"):
        if key not in fm or not fm[key].strip():
            raise SystemExit(f"Post frontmatter missing '{key}'")
    return fm


# ---------- payload ----------
def build_payload(author_urn, fm, url):
    """Put URL in commentary; let LinkedIn unfurl the OG card."""
    commentary = f"{fm['linkedinSummary'].strip()}\n\n{url}"
    if len(commentary) > MAX_COMMENTARY:
        raise SystemExit(
            f"commentary too long: {len(commentary)} > {MAX_COMMENTARY}. Trim linkedinSummary."
        )
    return {
        "author": author_urn,
        "commentary": commentary,
        "visibility": "PUBLIC",
        "distribution": {
            "feedDistribution": "MAIN_FEED",
            "targetEntities": [],
            "thirdPartyDistributionChannels": [],
        },
        "lifecycleState": "PUBLISHED",
        "isReshareDisabledByAuthor": False,
    }


def dry_run_print(payload, url):
    print("=" * 60)
    print("DRY RUN — would POST to:", LINKEDIN_API)
    print("=" * 60)
    print(f"URL (unfurled from commentary): {url}")
    print(f"Commentary ({len(payload['commentary'])} chars):")
    print("-" * 60)
    print(payload["commentary"])
    print("-" * 60)
    print("Full JSON payload:")
    print(json.dumps(payload, indent=2, ensure_ascii=False))
    print("=" * 60)
    print("✓ Dry run complete (no network call)")


def do_post(token, version, payload):
    body = json.dumps(payload).encode("utf-8")
    headers = {
        "Authorization": f"Bearer {token}",
        "Content-Type": "application/json",
        "LinkedIn-Version": version,
        "X-Restli-Protocol-Version": "2.0.0",
    }
    req = urllib.request.Request(LINKEDIN_API, data=body, headers=headers, method="POST")

    print(f"POST {LINKEDIN_API} …")
    try:
        with urllib.request.urlopen(req, timeout=30) as resp:
            post_urn = resp.headers.get("x-restli-id") or resp.headers.get("X-Restli-Id")
            print(f"✓ HTTP {resp.status}")
            if post_urn:
                print(f"✓ Post URN: {post_urn}")
                print(f"  https://www.linkedin.com/feed/update/{post_urn}/")
            return post_urn
    except urllib.error.HTTPError as e:
        body_text = e.read().decode("utf-8", "replace")
        print(f"✗ HTTP {e.code}", file=sys.stderr)
        print(body_text, file=sys.stderr)
        raise SystemExit(1)
    except urllib.error.URLError as e:
        raise SystemExit(f"Connection error: {e}")


# ---------- main ----------
def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--slug", required=True)
    parser.add_argument("--url-override")
    parser.add_argument("--post", action="store_true",
                        help="Actually POST to LinkedIn (default: dry run)")
    args = parser.parse_args()

    base = os.environ.get("POST_URL_BASE", DEFAULT_BASE).rstrip("/")
    url = args.url_override or f"{base}/blog/{args.slug}/"

    fm = load_post(args.slug)

    token = os.environ.get("LINKEDIN_ACCESS_TOKEN")
    author_urn = os.environ.get("LINKEDIN_AUTHOR_URN")
    version = os.environ.get("LINKEDIN_VERSION")

    if not args.post:
        # Dry run — dummy author so payload builds even without secrets
        payload = build_payload(author_urn or "urn:li:person:DRY-RUN", fm, url)
        dry_run_print(payload, url)
        return

    # Real post mode — all three env vars required
    missing = [n for n, v in (
        ("LINKEDIN_ACCESS_TOKEN", token),
        ("LINKEDIN_AUTHOR_URN", author_urn),
        ("LINKEDIN_VERSION", version),
    ) if not v]
    if missing:
        raise SystemExit(f"Missing env vars: {', '.join(missing)}")

    payload = build_payload(author_urn, fm, url)
    do_post(token, version, payload)


if __name__ == "__main__":
    main()
