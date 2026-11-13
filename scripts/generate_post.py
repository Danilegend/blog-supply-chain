#!/usr/bin/env python3
import argparse
import json
import os
import re
import sys
import time
import tomllib
import urllib.parse
import urllib.request
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
# Pexels Image Fetching
# ---------------------------------------------------------------------------
def fetch_pexels_images(query: str, count: int = 3):
    api_key = os.environ.get("PEXELS_API_KEY")
    if not api_key:
        print("  ⚠ PEXELS_API_KEY not set. Skipping image fetch.")
        return []

    clean_query = re.sub(r'[^a-zA-Z0-9 ]', '', query)[:50].strip()
    url = f"https://api.pexels.com/v1/search?query={urllib.parse.quote(clean_query)}&per_page={count}&orientation=landscape"
    
    # Pexels requires both an Authorization header and a User-Agent header.
    # The Authorization header must be the raw API key, without a "Bearer" prefix.
    headers = {
        "Authorization": api_key, 
        "User-Agent": "BlogSupplyChain/1.0 (https://github.com/Danilegend/blog-supply-chain)"
    }
    req = urllib.request.Request(url, headers=headers)
    
    try:
        with urllib.request.urlopen(req, timeout=10) as resp:
            data = json.loads(resp.read().decode("utf-8"))
            images = [photo["src"]["large"] for photo in data.get("photos", [])]
            print(f"  ✓ Fetched {len(images)} images from Pexels")
            return images
    except urllib.error.HTTPError as e:
        print(f"  ⚠ Pexels API error: HTTP {e.code}")
        # Print the response body for more details
        print(f"     Response: {e.read().decode('utf-8', 'replace')[:200]}")
        return []
    except Exception as e:
        print(f"  ⚠ Pexels API error: {e}")
        return []

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

    raise SystemExit(f"All models exhausted. Last error: {last_error}")

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
        raise SystemExit(f"JSON parse failed: {e}\nRaw: {raw}")

    for key in ("title", "description", "body", "linkedin_summary"):
        if key not in data or not data[key].strip():
            raise SystemExit(f"Writer JSON missing key: {key}")

    print(f"✓ Writer produced: {data['title']}")
    return data

# ---------------------------------------------------------------------------
# Affiliates
# ---------------------------------------------------------------------------
def load_affiliates():
    if not AFFILIATES_CONFIG.exists():
        return {}
    with AFFILIATES_CONFIG.open("rb") as f:
        return tomllib.load(f)

def affiliate_link_html(entry, anchor=None):
    name = anchor if anchor else entry.get("name", "Link")
    url = entry.get("url", "#")
    return f'<a href="{url}" rel="sponsored nofollow noopener" target="_blank">{name}</a>'

def replace_affiliate_links(body):
    affiliates = load_affiliates()
    default = affiliates.get("default", {"name": "Product", "url": "#"})
    products = {k: v for k, v in affiliates.items() if k != "default"}
    count = 0

    def _sub(m):
        nonlocal count
        count += 1
        if m.group(0) == "[AFFILIATE_LINK]":
            return affiliate_link_html(default)
        slug, anchor = m.group(1), m.group(2)
        if slug not in products:
            return m.group(0) # Leave alone if unknown
        return affiliate_link_html(products[slug], anchor)

    return PLACEHOLDER_RE.sub(_sub, body), count

# ---------------------------------------------------------------------------
# Write
# ---------------------------------------------------------------------------
def slugify(title):
    return re.sub(r"[^a-z0-9]+", "-", title.lower()).strip("-")

def render_frontmatter(data, images):
    today = date.today().isoformat()
    q = lambda s: s.replace('"', '\\"')
    
    fm = (
        "---\n"
        f'title: "{q(data["title"])}"\n'
        f'description: "{q(data["description"])}"\n'
        f"pubDate: {today}\n"
        f'linkedinSummary: "{q(data["linkedin_summary"])}"\n'
        "affiliateDisclosure: true\n"
        "draft: false\n"
    )
    if images:
        fm += "images:\n"
        for img in images:
            fm += f'  - "{img}"\n'
    fm += "---\n\n"
    return fm

def write_post(data):
    POSTS_DIR.mkdir(parents=True, exist_ok=True)
    slug = slugify(data["title"])
    out_path = POSTS_DIR / f"{slug}.md"

    if out_path.exists():
        raise SystemExit(f"Refusing to overwrite: {out_path}")

    body, count = replace_affiliate_links(data["body"])
    if count == 0:
        print("  ⚠ warning: no affiliate placeholder found")

    # Fetch images based on the title
    images = fetch_pexels_images(data["title"], count=3)

    content = render_frontmatter(data, images) + body
    out_path.write_text(content, encoding="utf-8")
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
            retry_options=types.HttpRetryOptions(attempts=7, initial_delay=5.0, max_delay=120.0, jitter=2.0),
        ),
    )

    outline = run_strategist(client, args.topic)
    data = run_writer(client, outline)
    path = write_post(data)

    print(f"\n✓ Wrote: {path}")
    print(f"  Next: npm run build")

if __name__ == "__main__":
    main()
