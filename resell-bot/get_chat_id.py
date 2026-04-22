#!/usr/bin/env python3
"""
Helper script to find your Telegram Chat ID.

How to use:
  1. Open Telegram and send any message to your bot (press Start if first time)
  2. Run:  python get_chat_id.py
  3. Copy the Chat ID number shown
  4. Add it as TELEGRAM_CHAT_ID in GitHub → Settings → Secrets → Actions
"""

import os
import sys
import requests


def main():
    token = os.environ.get("TELEGRAM_BOT_TOKEN")
    if not token:
        token = input("Paste your TELEGRAM_BOT_TOKEN here: ").strip()

    if not token:
        print("ERROR: No token provided.")
        sys.exit(1)

    url = f"https://api.telegram.org/bot{token}/getUpdates"
    try:
        resp = requests.get(url, timeout=10)
        data = resp.json()
    except Exception as e:
        print(f"ERROR: Could not contact Telegram: {e}")
        sys.exit(1)

    if not data.get("ok"):
        print(f"ERROR: Telegram returned an error: {data.get('description', 'unknown')}")
        print("Make sure your bot token is correct.")
        sys.exit(1)

    results = data.get("result", [])
    if not results:
        print("No messages found yet.")
        print("→ Open Telegram, find your bot, and press START (or send any message).")
        print("→ Then run this script again.")
        sys.exit(0)

    # Extract unique chat IDs
    chats = {}
    for update in results:
        msg = update.get("message") or update.get("channel_post") or {}
        chat = msg.get("chat", {})
        chat_id = chat.get("id")
        chat_title = chat.get("title") or chat.get("username") or chat.get("first_name", "")
        if chat_id:
            chats[chat_id] = chat_title

    if not chats:
        print("Could not extract a chat ID from the updates.")
        sys.exit(1)

    print("\n" + "=" * 50)
    print("Your Telegram Chat ID(s):")
    print("=" * 50)
    for chat_id, name in chats.items():
        print(f"  {chat_id}  <- {name}")
    print("=" * 50)
    print("\nCopy the number above, then add it as:")
    print("  GitHub -> Settings -> Secrets -> Actions -> New secret")
    print("  Name:  TELEGRAM_CHAT_ID")
    print(f"  Value: {list(chats.keys())[0]}")


if __name__ == "__main__":
    main()
