---
name: voice-edge-services
description: Use when interacting with voice-edge services — Pi (knives-edge), 4090 STT/TTS, Mac mic recording, or any endpoint requiring API keys from .env files.
---

# Voice-Edge Services

## Overview

Voice assistant pipeline across three hosts. All authenticated endpoints use keys from `/Users/aleiby/openclaw/.env`.

## CRITICAL: .env Safety

**NEVER read `/Users/aleiby/openclaw/.env` directly** — contents go into session logs and leak secrets.

**Always source and interpolate:**
```bash
source /Users/aleiby/openclaw/.env 2>/dev/null
curl -s ... -H "X-Edge-Key: $EDGE_API_KEY"
```

This keeps secrets out of logs. The `2>/dev/null` suppresses warnings from unquoted values in the file.

## Service Map

| Service | Host | Port | Auth Header |
|---------|------|------|-------------|
| Pi (knives-edge) | `knives-edge.local` | 9300 | `X-Edge-Key` |
| 4090 STT | `192.168.5.150` | 9100 | none |
| 4090 TTS | `192.168.5.150` | 9200 | none |
| Mac mic | `aarons-macbook-pro.local` | 9400 | `X-Api-Key` |
| OpenClaw | `aarons-macbook-pro.local` | 18789 | Bearer token |

## Quick Reference

### STT (Speech-to-Text)
```bash
curl -s -X POST http://192.168.5.150:9100/stt \
  -F "audio=@/tmp/recording.wav" \
  -F "prompt=Timer commands with numbers"
```
Returns JSON: `{"ok": true, "text": "...", "decode_ms": N}`

### TTS (Text-to-Speech) + Playback
macOS must do both fetch and playback (FUSE/pipes don't work with `afplay`):
```bash
mac bash -c 'curl -s -X POST http://192.168.5.150:9200/tts \
  -H "Content-Type: application/json" \
  -d "{\"text\":\"Hello\"}" \
  --output "$TMPDIR/tts.wav" && afplay "$TMPDIR/tts.wav"'
```

### Mac Mic Recording
Service runs on macOS (launched from Terminal.app for TCC mic permission):
```bash
source /Users/aleiby/openclaw/.env 2>/dev/null
curl -s -X POST http://aarons-macbook-pro.local:9400/record \
  -H "X-Api-Key: $EDGE_API_KEY" \
  -H "Content-Type: application/json" \
  -d '{"duration": 5}' --output /tmp/recording.wav
```
Headers `X-Mean-Volume` and `X-Max-Volume` in response indicate audio levels (-91 dB = silence).

### Pi Endpoints (all require `X-Edge-Key`)
```bash
source /Users/aleiby/openclaw/.env 2>/dev/null
# Health
curl -s http://knives-edge.local:9300/health
# Deploy (git pull + restart services)
curl -s -X POST http://knives-edge.local:9300/deploy -H "X-Edge-Key: $EDGE_API_KEY"
# Wake metrics
curl -s "http://knives-edge.local:9300/metrics/wake?limit=10" -H "X-Edge-Key: $EDGE_API_KEY"
# Intent metrics
curl -s "http://knives-edge.local:9300/metrics/intent?limit=10" -H "X-Edge-Key: $EDGE_API_KEY"
# Volume
curl -s http://knives-edge.local:9300/volume/status -H "X-Edge-Key: $EDGE_API_KEY"
curl -s -X POST http://knives-edge.local:9300/volume/set -H "X-Edge-Key: $EDGE_API_KEY" \
  -H "Content-Type: application/json" -d '{"percent": 70}'
```

## Closed-Loop Testing Pattern

Record Mac mic in background while playing TTS through Mac speakers. Pi picks up wake word via Anker speakerphone, responds, Mac mic captures response, STT verifies.

```bash
source /Users/aleiby/openclaw/.env 2>/dev/null
# Background: record 20s
curl -s -X POST "http://aarons-macbook-pro.local:9400/record" \
  -H "X-Api-Key: $EDGE_API_KEY" -H "Content-Type: application/json" \
  -d '{"duration": 20}' --output /tmp/loop_test.wav &
sleep 2
# Play wake command through Mac speakers
mac bash -c 'curl -s -X POST http://192.168.5.150:9200/tts \
  -H "Content-Type: application/json" \
  -d "{\"text\":\"Hey Jarvis, what time is it?\"}" \
  --output "$TMPDIR/tts.wav" && afplay "$TMPDIR/tts.wav"'
wait
# Transcribe captured audio
curl -s -X POST http://192.168.5.150:9100/stt -F "audio=@/tmp/loop_test.wav"
```

Wake word: **"Hey Jarvis"** (model: `hey_jarvis`, threshold: 0.78)

## Mac Mic Service Setup

Only needed once per Mac reboot:
1. Grant Terminal.app microphone permission in System Settings > Privacy & Security > Microphone
2. Restart Terminal.app after granting
3. In Terminal: `set -a && source ~/openclaw/.env && set +a && python3 ~/mac_mic_service.py`

Source: `voice-edge/mac_mic_service.py`
