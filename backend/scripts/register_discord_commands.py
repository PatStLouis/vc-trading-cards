#!/usr/bin/env python3
"""
Register Discord slash commands for Tritone Cards bot.
Run once after setting DISCORD_CLIENT_ID and DISCORD_BOT_TOKEN.

  cd backend && uv run python scripts/register_discord_commands.py

In Discord Developer Portal:
  1. Bot → Reset Token and copy as DISCORD_BOT_TOKEN
  2. General → Application ID is DISCORD_CLIENT_ID
  3. General → Public Key is DISCORD_PUBLIC_KEY (for interaction verification)
  4. Interactions Endpoint URL → set to https://your-backend.example.com/discord/interactions
"""
import os
import sys

import httpx

APPLICATION_ID = os.getenv("DISCORD_CLIENT_ID", "").strip()
BOT_TOKEN = os.getenv("DISCORD_BOT_TOKEN", "").strip()
if not APPLICATION_ID or not BOT_TOKEN:
    print("Set DISCORD_CLIENT_ID and DISCORD_BOT_TOKEN", file=sys.stderr)
    sys.exit(1)

URL = f"https://discord.com/api/v10/applications/{APPLICATION_ID}/commands"

COMMANDS = [
    {
        "name": "wallet",
        "description": "Open your Tritone Cards deck (The Devil's Interval Collectible Cards)",
        "type": 1,
    },
    {
        "name": "collection",
        "description": "View your Tritone Cards collection",
        "type": 1,
    },
]


def main():
    with httpx.Client() as client:
        for cmd in COMMANDS:
            r = client.post(
                URL,
                headers={
                    "Authorization": f"Bot {BOT_TOKEN}",
                    "Content-Type": "application/json",
                },
                json=cmd,
            )
            r.raise_for_status()
            print("Registered:", r.json().get("name", cmd["name"]))
    print("Done. Set Interactions Endpoint URL in Discord Developer Portal to your backend /discord/interactions URL.")


if __name__ == "__main__":
    main()
