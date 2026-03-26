---
name: telegram-notify
description: Use when needing to send Telegram messages or notifications to the user via the OpenClaw gateway.
---

# Telegram Notifications via OpenClaw

## Overview

Send Telegram DMs to the user through the OpenClaw chat completions API. OpenClaw has a Telegram extension that can send messages when asked. The user's Telegram ID is stored in `~/.openclaw/openclaw.json` within OpenClaw's environment (not the local machine).

## Quick Reference

| Detail | Value |
|--------|-------|
| OpenClaw endpoint | `http://aarons-macbook-pro.local:18789/v1/chat/completions` |
| Auth token source | `OPENCLAW_GATEWAY_TOKEN` from `/Users/aleiby/openclaw/.env` |
| Token value | Read from `.env` at runtime: `grep OPENCLAW_GATEWAY_TOKEN /Users/aleiby/openclaw/.env` |
| Telegram user ID | `8315690849` (cached; canonical source: `~/.openclaw/openclaw.json` in OpenClaw's env) |
| User ID locations in config | `channels.telegram.groupAllowFrom`, `tools.elevated.allowFrom.telegram`, `agents.list[0].tools.elevated.allowFrom.telegram` |

## The Working Pattern

Use a **fresh session key** for each message (append timestamp). Ask OpenClaw to find the Telegram user ID from its own config file and send the DM. Keep messages **short** (under ~30 words) to avoid internal timeout.

```bash
curl -s -X POST 'http://aarons-macbook-pro.local:18789/v1/chat/completions' \
  -H 'Authorization: Bearer TOKEN_HERE' \
  -H 'Content-Type: application/json' \
  -H "x-openclaw-session-key: notify-$(date +%s)" \
  --data-raw '{"messages":[{"role":"user","content":"Find Telegram user ID in ~/.openclaw/openclaw.json and DM them: YOUR_MESSAGE_HERE"}]}' \
  --max-time 90
```

### Fully scripted (read token from .env):

```bash
TOKEN=$(grep OPENCLAW_GATEWAY_TOKEN /Users/aleiby/openclaw/.env | cut -d= -f2)
MSG="Your short message here"
curl -s -X POST 'http://aarons-macbook-pro.local:18789/v1/chat/completions' \
  -H "Authorization: Bearer $TOKEN" \
  -H 'Content-Type: application/json' \
  -H "x-openclaw-session-key: notify-$(date +%s)" \
  --data-raw "{\"messages\":[{\"role\":\"user\",\"content\":\"Find Telegram user ID in ~/.openclaw/openclaw.json and DM them: $MSG\"}]}" \
  --max-time 90
```

## Important Notes

- **Push-only**: The user cannot respond via Telegram. This is a one-way notification channel. Do not expect replies or ask questions.

## Gotchas

- **Fresh session key required**: Reusing session keys with tool-use conversations causes timeouts. Always use a unique key (e.g., `notify-$(date +%s)`).
- **Keep messages short**: Messages over ~30 words tend to cause OpenClaw internal timeout ("No response from OpenClaw"). Split long updates into multiple sends if needed.
- **"No response from OpenClaw"**: This is the timeout fallback. The message likely did NOT send. Retry with a shorter message and fresh session key.
- **Ask OpenClaw to find the ID**: Even though we know the ID is `8315690849`, the reliable pattern is to ask OpenClaw to read `~/.openclaw/openclaw.json` itself. Direct ID references sometimes work but are less reliable.
- **Single quotes for curl**: Use single quotes around the URL and headers to avoid shell escaping issues.
