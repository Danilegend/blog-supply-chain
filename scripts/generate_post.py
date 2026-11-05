#!/usr/bin/env python3
"""
Phase 2, Bite 2: Gemini-powered post generator (local only).

Two-stage generation:
  1. Strategist: topic -> outline
  2. Writer: outline -> {title, description, body, linkedin_summary}

Writes a Markdown file into src/content/posts/.
Reads GEMINI_API_KEY from the environment. Never hardcode the key.
"""

import argparse
import json
import os
import re
import sys
from datetime import date
from pathlib import Path
import time
from google.genai import errors

from google import genai

ROOT = Path(__file__).resolve().parent.parent
PROMPTS = Path(__file__).resolve().parent / "prompts"
POSTS_DIR = ROOT / "src" / "content" / "posts"

MODEL = os.environ.get("GEMINI_MODEL", "gemini-3.5-flash-lite")  # free-tier eligible; switch to gemini-3.5-flash-lite if unavailable


def slugify(title: str) -> str:
    slug = title.lower()
    slug = re.sub(r"[^a-z0-9]+", "-", slug).strip("-")
    return slug



def call_gemini(client, system_prompt, user_input, max_retries=3):
    for attempt in range(max_retries):
        try:
            response = client.models.generate_content(
                model=MODEL,
                contents=f"{system_prompt}\n\n---\n\n{user_input}",
            )
            return response.text
        except errors.ServerError as e:
            if attempt < max_retries - 1:
                wait = 2 ** attempt * 5  # 5s, 10s, 20s
                print(f"  Server busy (503), retrying in {wait}s...")
                time.sleep(wait)
            else:
                raise SystemExit(f"Gemini API unavailable after {max_retries} retries: {e}")


def run_strategist(client: genai.Client, topic: str) -> str:
    prompt = (PROMPTS / "strategist.txt").read_text(encoding="utf-8")
    outline = call_gemini(client, prompt, f"Topic: {topic}")
    print(f"✓ Strategist produced outline ({len(outline)} chars)")
    return outline


def run_writer(client: genai.Client, outline: str) -> dict:
    prompt = (PROMPTS / "writer.txt").read_text(encoding="utf-8")
    raw = call_gemini(client, prompt, f"Outline:\n\n{outline}")

    # Strip accidental markdown fences if the model wrapped the JSON
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


def render_frontmatter(data: dict) -> str:
    today = date.today().isoformat()
    # Escape double quotes inside values so YAML stays valid
    def q(s: str) -> str:
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


def write_post(data: dict) -> Path:
    POSTS_DIR.mkdir(parents=True, exist_ok=True)
    slug = slugify(data["title"])
    out_path = POSTS_DIR / f"{slug}.md"

    if out_path.exists():
        raise SystemExit(
            f"Refusing to overwrite existing post: {out_path}\n"
            "Change the title or delete the existing file."
        )

    out_path.write_text(render_frontmatter(data) + data["body"], encoding="utf-8")
    return out_path


def main() -> None:
    parser = argparse.ArgumentParser(description="Generate a blog post with Gemini.")
    parser.add_argument("--topic", required=True, help="Topic for the post")
    args = parser.parse_args()

    api_key = os.environ.get("GEMINI_API_KEY")
    if not api_key:
        raise SystemExit(
            "GEMINI_API_KEY is not set.\n"
            "Run: export GEMINI_API_KEY=\"your-key-here\"\n"
            "Do NOT paste the key into any file in this repo."
        )

    client = genai.Client(api_key=api_key)

    outline = run_strategist(client, args.topic)
    data = run_writer(client, outline)
    path = write_post(data)

    print(f"\n✓ Wrote: {path}")
    print(f"  Slug: {path.stem}")
    print("  Next: npm run build")


if __name__ == "__main__":
    main()
