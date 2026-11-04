#!/usr/bin/env python3
"""
Phase 2, Bite 1: Standalone post generator (canned draft, no API).

Writes a Markdown file into src/content/posts/ with proper frontmatter.
No network, no API key, no Gemini. Proves the write -> build loop.
"""

import re
from datetime import date
from pathlib import Path

# ---------------------------------------------------------------------------
# Canned draft (will be replaced by Gemini output in the next bite)
# ---------------------------------------------------------------------------
DRAFT = {
    "title": "Why Content Supply Chains Beat Content Calendars",
    "description": "A calendar tells you when to publish. A supply chain tells you what to publish, why, and how it connects to revenue.",
    "linkedin_summary": "Most teams treat content like a calendar problem. The ones that win treat it like a supply chain — inputs, transformations, quality gates, distribution. Here's the difference and why it compounds.",
    "body": """## The calendar trap

A content calendar answers one question: *when do we publish?* It says nothing about whether the post will rank, convert, or connect to anything you sell.

## The supply chain view

A content supply chain has four stages:

1. **Inputs** — topic research, keyword gaps, product hooks
2. **Transformation** — drafting, editing, SEO passes
3. **Quality gates** — human approval before anything ships
4. **Distribution** — blog, then social, then email

Each stage has a pass/fail condition. Nothing moves forward on vibes.

## Why it compounds

When every post feeds the next one — internal links, canonical topics, a consistent affiliate stack — the output is greater than the sum of the parts. A calendar just produces posts. A supply chain produces an asset.

Try [AFFILIATE_LINK] if you want the full framework.
""",
}


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------
def slugify(title: str) -> str:
    slug = title.lower()
    slug = re.sub(r"[^a-z0-9]+", "-", slug)
    slug = slug.strip("-")
    return slug


def render_frontmatter(draft: dict) -> str:
    # YAML frontmatter. Values are quoted to be safe with special chars.
    today = date.today().isoformat()
    return (
        "---\n"
        f'title: "{draft["title"]}"\n'
        f'description: "{draft["description"]}"\n'
        f"pubDate: {today}\n"
        f'linkedinSummary: "{draft["linkedin_summary"]}"\n'
        "affiliateDisclosure: true\n"
        "draft: false\n"
        "---\n\n"
    )


def write_post(draft: dict) -> Path:
    slug = slugify(draft["title"])
    out_dir = Path(__file__).resolve().parent.parent / "src" / "content" / "posts"
    out_dir.mkdir(parents=True, exist_ok=True)
    out_path = out_dir / f"{slug}.md"

    if out_path.exists():
        raise SystemExit(
            f"Refusing to overwrite existing post: {out_path}\n"
            "Delete it first or change the title."
        )

    content = render_frontmatter(draft) + draft["body"]
    out_path.write_text(content, encoding="utf-8")
    return out_path


def main() -> None:
    path = write_post(DRAFT)
    print(f"✓ Wrote post: {path}")
    print(f"  Slug: {path.stem}")
    print(f"  Next: run `npm run build` and check dist/blog/")


if __name__ == "__main__":
    main()
