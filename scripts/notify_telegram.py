#!/usr/bin/env python3
"""
Phase 3, Bite 1: Send a Telegram message.

Reads TELEGRAM_BOT_TOKEN and TELEGRAM_CHAT_ID from the environment.
No polling, no approval handling — just send.
"""

import argparse
import json
import os
import sys
import urllib.error
import urllib.request

API = "https://api.telegram.org/bot{token}/sendMessage"


def send_message(token, chat_id, text):
    payload = json.dumps({
        "chat_id": chat_id,
        "text": text,
        "parse_mode": "HTML",
        "disable_web_page_preview": True,
    }).encode("utf-8")

    req = urllib.request.Request(
        API.format(token=token),
        data=payload,
        headers={"Content-Type": "application/json"},
        method="POST",
    )

    try:
        with urllib.request.urlopen(req, timeout=15) as resp:
            data = json.loads(resp.read().decode("utf-8"))
            if not data.get("ok"):
                raise SystemExit(f"Telegram API not ok: {data}")
            return data["result"]["message_id"]
    except urllib.error.HTTPError as e:
        body = e.read().decode("utf-8", "replace")
        raise SystemExit(f"Telegram HTTP {e.code}: {body}")
    except urllib.error.URLError as e:
        raise SystemExit(f"Telegram connection error: {e}")


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--message", required=True, help="Message text (HTML allowed)")
    args = parser.parse_args()

    token = os.environ.get("TELEGRAM_BOT_TOKEN")
    chat_id = os.environ.get("TELEGRAM_CHAT_ID")
    if not token:
        raise SystemExit("TELEGRAM_BOT_TOKEN is not set.")
    if not chat_id:
        raise SystemExit("TELEGRAM_CHAT_ID is not set.")

    mid = send_message(token, chat_id, args.message)
    print(f"✓ Sent. message_id={mid}")


if __name__ == "__main__":
    main()
