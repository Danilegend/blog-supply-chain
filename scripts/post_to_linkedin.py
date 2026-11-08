#!/usr/bin/env python3
"""
Phase 4, Bite 1: LinkedIn cross-post (DRY RUN only).

Reads a post's frontmatter (linkedinSummary + title), builds the
text that would be posted to LinkedIn, and prints it.

Does NOT call the LinkedIn API in this bite.

Usage:
  python3 scripts/post_to_linkedin.py --slug <post-slug>
  python3 scripts/post_to_linkedin.py --slug <slug> --url-override <full-url>

Reads POST_URL_BASE from env, default derived from known GitHub Pages URL.
"""

import argparse
import os
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
POSTS_DIR = ROOT / "src" / "content" / "posts"

# Default base matches your current GitHub Pages project URL.
# Override with POST_URL_BASE when you add a custom domain.
DEFAULT_BASE = "https://Danilegend.github.io/blog-supply-chain"

# Frontmatter is simple key: "quoted value" — minimal parser, no YAML dep.
FM_RE = re.compile(r'^([A-Za-z_][A-Za-z0-9_]*):\s*"?(.*?)"?\s*$')

# LinkedIn max post length (text only, no URL preview overhead)
MAX_LEN = 3000


def parse_frontmatter(text: str):
    if not text.startswith("---"):
        raise SystemExit("File does not start with ---")
    end = text.find("\n---", 4)
    if end == -1:
        raise SystemExit("File has no closing ---")
    fm_raw = text[4:end].strip().splitlines()
    data = {}
    for line in fm_raw:
        m = FM_RE.match(line.strip())
        if not m:
            continue
        key, val = m.group(1), m.group(2)
        # unescape simple \" from frontmatter writer
        val = val.replace('\\"', '"')
        data[key] = val
    return data


def load_post(slug: str):
    # Slug may or may not include .md
    filename = slug if slug.endswith(".md") else f"{slug}.md"
    path = POSTS_DIR / filename
    if not path.exists():
        raise SystemExit(f"Post not found: {path}")
    text = path.read_text(encoding="utf-8")
    fm = parse_frontmatter(text)
    for key in ("title", "linkedinSummary"):
        if key not in fm or not fm[key].strip():
            raise SystemExit(f"Post frontmatter missing '{key}'")
    return fm


def build_post_text(fm, url):
    summary = fm["linkedinSummary"].strip()
    # LinkedIn's link preview replaces the URL with a card; still include it in text.
    body = f"{summary}\n\n{url}"
    return body


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--slug", required=True, help="Post slug (file name without .md)")
    parser.add_argument("--url-override", help="Full URL to use instead of derived one")
    parser.add_argument("--print-only", action="store_true", default=True,
                        help="Print only (this bite is dry-run only)")
    args = parser.parse_args()

    base = os.environ.get("POST_URL_BASE", DEFAULT_BASE).rstrip("/")
    url = args.url_override or f"{base}/blog/{args.slug}/"

    fm = load_post(args.slug)
    text = build_post_text(fm, url)

    print("=" * 60)
    print("DRY RUN — would post the following to LinkedIn:")
    print("=" * 60)
    print(text)
    print("=" * 60)
    print(f"Length: {len(text)} chars (LinkedIn limit ~{MAX_LEN})")
    print(f"URL: {url}")

    if len(text) > MAX_LEN:
        raise SystemExit(f"\n✗ Too long by {len(text) - MAX_LEN} chars — trim the summary.")

    print("\n✓ Ready (no network call made)")


if __name__ == "__main__":
    main()
