#!/usr/bin/env python3
"""
Phase 2, Bite 3 (revised): Gemini post generator with retry + model fallback.
"""

import argparse
import json
import os
import re
import sys
import time
from datetime import date
from pathlib import Path

from google import genai
from google.genai import types, errors

ROOT = Path(__file__).resolve().parent.parent
PROMPTS = Path(__file__).resolve().parent / "prompts"
POSTS_DIR = ROOT / "src" / "content" / "posts"

# Model fallback chain: try each in order until one succeeds.
# Primary from env (default gemini-3.5-flash-lite), then stable fallbacks.
MODEL_CHAIN = [
    os.environ.get("GEMINI_MODEL", "gemini-3.5-flash-lite"),
    "gemini-3.6-flash",
    "gemini-3.1-flash-lite",
    "gemini-2.0-flash",
]


def slugify(title: str) -> str:
    slug = title.lower()
    slug = re.sub(r"[^a-z0-9]+", "-", slug).strip("-")
    return slug


def call_gemini(client: genai.Client, system_prompt: str, user_input: str) -> str:
    """
    Try each model in the chain. The SDK's HttpRetryOptions handles
    exponential-backoff retries on 503/5xx before we move to the next model.
    """
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
            # 503 after all SDK retries exhausted — try next model
            print(f"  ✗ {model} unavailable after retries: {e}")
            last_error = e
            # small pause before trying next model
            time.sleep(3)
        except errors.APIError as e:
            # Non-retryable (e.g. 400, 403, 404) — fail fast, don't rotate models
            raise SystemExit(f"Gemini API error on {model}: {e}")

    raise SystemExit(
        f"All models in chain exhausted. Last error: {last_error}\n"
        f"Chain: {MODEL_CHAIN}"
    )


def run_strategist(client: genai.Client, topic: str) -> str:
    prompt = (PROMPTS / "strategist.txt").read_text(encoding="utf-8")
    outline = call_gemini(client, prompt, f"Topic: {topic}")
    print(f"✓ Strategist produced outline ({len(outline)} chars)")
    return outline


def run_writer(client: genai.Client, outline: str) -> dict:
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


def render_frontmatter(data: dict) -> str:
    today = date.today().isoformat()

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
            'Run: export GEMINI_API_KEY="your-key-here"'
        )

    # Configure SDK-level retry with more patience for CI environments
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