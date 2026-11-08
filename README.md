# Blog Supply Chain

An autonomous AI content pipeline built with Astro, GitHub Actions, Gemini, and Telegram.

## How it works

1. **Generate:** Trigger the `Generate Draft Post` workflow in GitHub Actions.
2. **Review:** The system generates a draft, opens a Pull Request, and pings you on Telegram.
3. **Approve:** Merge the Pull Request on GitHub.
4. **Publish:** Astro automatically deploys the site to GitHub Pages.
5. **Cross-post:** A GitHub Action detects the new post, waits for the URL to go live, and posts it to LinkedIn with a rich preview card.

## Local Development

```bash
# Install dependencies
npm install

# Start dev server
npm run dev

# Run the AI generator locally (requires GEMINI_API_KEY)
source .venv/bin/activate
export GEMINI_API_KEY="your-key"
python3 scripts/generate_post.py --topic "Your topic here"
