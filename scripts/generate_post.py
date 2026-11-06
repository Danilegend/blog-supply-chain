#!/usr/bin/env python3
"""
Phase 2, Bite 4: Gemini post generator with retry + model fallback + affiliate links.
"""

import argparse
import json
import os
import re
import sys
import time
import tomllib
from datetime import date
from pathlib import Path

from google import genai
from google.genai import types, errors

ROOT = Path(__file__).resolve().parent.parent
PROMPTS = Path(__file__).resolve().parent / "prompts"
POSTS_DIR = ROOT / "src" / "content" / "posts"
AFFILIATES_CONFIG = ROOT / "config" / "affiliates.toml"

MODEL_CHAIN = [
    os.environ.get("GEMINI_MODEL", "gemini-3.5-flash-lite"),
    "gemini-3.6-flash",
    "gemini-3.1-flash-lite",
    "gemini-2.0-flash",
]

PLACEHOLDER_RE = re.compile(
    r"\[AFFILIATE_LINK\]"
    r"|\[AFFILIATE:([a-z0-9\-]+)(?:\|([^\]]+))?\]"
)


# ---------------------------------------------------------------------------
# Gemini
# ---------------------------------------------------------------------------
def call_gemini(client, system_prompt, user_input):
    last_error = None
    for model in MODEL_CHAIN:
        try:
            response = client.models.generate_content(
                model=model,
                contents=f"{system_prompt}\n\n---\n\n{user_input}",
            )
            print(f"  ✓ {model} succeeded")
            return response.text
        except errors.ServerError as e:
            print(f"  ✗ {model} unavailable after retries: {e}")
            last_error = e
            time.sleep(3)
        except errors.APIError as e:
            raise SystemExit(f"Gemini API error on {model}: {e}")

    raise SystemExit(
        f"All models in chain exhausted. Last error: {last_error}\n"
        f"Chain: {MODEL_CHAIN}"
    )


def run_strategist(client, topic):
    prompt = (PROMPTS / "strategist.txt").read_text(encoding="utf-8")
    outline = call_gemini(client, prompt, f"Topic: {topic}")
    print(f"✓ Strategist produced outline ({len(outline)} chars)")
    return outline


def run_writer(client, outline):
    prompt = (PROMPTS / "writer.txt").read_text(encoding="utf-8")
    raw = call_gemini(client, prompt, f"Outline:\n\n{outline}")

    cleaned = raw.strip()
    if cleaned.startswith("```"):
        cleaned = re.sub(r"^```[a-z]*\n?", "", cleaned)
        cleaned = re.sub(r"\n?```$", "", cleaned)

    try:
        data = json.loads(cleaned)
    except json.JSONDecodeError as e:
        print("Writer returned invalid JSON. Raw output:\n", file=sys.stderr)
        print(raw, file=sys.stderr)
        raise SystemExit(f"JSON parse failed: {e}")

    for key in ("title", "description", "body", "linkedin_summary"):
        if key not in data or not isinstance(data[key], str) or not data[key].strip():
            raise SystemExit(f"Writer JSON missing or empty key: {key}")

    print(f"✓ Writer produced: {data['title']}")
    return data


# ---------------------------------------------------------------------------
# Affiliate links
# ---------------------------------------------------------------------------
def load_affiliates():
    if not AFFILIATES_CONFIG.exists():
        raise SystemExit(f"Missing affiliate config: {AFFILIATES_CONFIG}")
    with AFFILIATES_CONFIG.open("rb") as f:
        return tomllib.load(f)


def _html_escape(s):
    return s.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")


def affiliate_link_html(entry, anchor=None):
    name = anchor if anchor else entry["name"]
    url = entry["url"]
    return (
        f'<a href="{url}" rel="sponsored nofollow noopener" '
        f'target="_blank">{_html_escape(name)}</a>'
    )


def replace_affiliate_links(body):
    affiliates = load_affiliates()
    default = affiliates.get("default")
    if default is None:
        raise SystemExit(f"{AFFILIATES_CONFIG} is missing a [default] entry.")
    products = {k: v for k, v in affiliates.items() if k != "default"}

    count = 0

    def _sub(m):
        nonlocal count
        count += 1
        if m.group(0) == "[AFFILIATE_LINK]":
            return affiliate_link_html(default)
        slug, anchor = m.group(1), m.group(2)
        if slug not in products:
            raise SystemExit(
                f"Unknown affiliate slug '{slug}'. "
                f"Add it to {AFFILIATES_CONFIG} or fix the placeholder."
            )
        return affiliate_link_html(products[slug], anchor)

    return PLACEHOLDER_RE.sub(_sub, body), count


# ---------------------------------------------------------------------------
# Post writing
# ---------------------------------------------------------------------------
def slugify(title):
    slug = title.lower()
    slug = re.sub(r"[^a-z0-9]+", "-", slug).strip("-")
    return slug


def render_frontmatter(data):
    today = date.today().isoformat()

    def q(s):
        return s.replace('"', '\\"')

    return (
        "---\n"
        f'title: "{q(data["title"])}"\n'
        f'description: "{q(data["description"])}"\n'
        f"pubDate: {today}\n"
        f'linkedinSummary: "{q(data["linkedin_summary"])}"\n'
        "affiliateDisclosure: true\n"
        "draft: false\n"
        "---\n\n"
    )


def write_post(data):
    POSTS_DIR.mkdir(parents=True, exist_ok=True)
    slug = slugify(data["title"])
    out_path = POSTS_DIR / f"{slug}.md"

    if out_path.exists():
        raise SystemExit(
            f"Refusing to overwrite existing post: {out_path}\n"
            "Change the title or delete the existing file."
        )

    body, count = replace_affiliate_links(data["body"])
    if count == 0:
        print("  ⚠ warning: no affiliate placeholder found in body")

    out_path.write_text(render_frontmatter(data) + body, encoding="utf-8")
    print(f"  ✓ replaced {count} affiliate placeholder(s)")
    return out_path


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--topic", required=True)
    args = parser.parse_args()

    api_key = os.environ.get("GEMINI_API_KEY")
    if not api_key:
        raise SystemExit("GEMINI_API_KEY is not set.")

    client = genai.Client(
        api_key=api_key,
        http_options=types.HttpOptions(
            retry_options=types.HttpRetryOptions(
                attempts=7,
                initial_delay=5.0,
                max_delay=120.0,
                exp_base=2.0,
                jitter=2.0,
                http_status_codes=[408, 429, 500, 502, 503, 504],
            )
        ),
    )

    outline = run_strategist(client, args.topic)
    data = run_writer(client, outline)
    path = write_post(data)

    print(f"\n✓ Wrote: {path}")
    print(f"  Slug: {path.stem}")
    print("  Next: npm run build")


if __name__ == "__main__":
    main()
