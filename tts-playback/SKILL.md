---
name: tts-playback
description: Use when needing to speak text aloud, play audio, or provide voice output from an OrbStack Linux VM.
---

# TTS Playback (OrbStack -> macOS)

## Overview

The voice-edge TTS service runs on the Windows 4090 host. OrbStack Linux VMs have no audio devices, so playback must happen on the macOS host via the `mac` bridge command.

## Quick Reference

| Detail | Value |
|--------|-------|
| TTS endpoint | `http://192.168.5.150:9200/tts` |
| Method | `POST`, JSON body `{"text": "..."}` |
| Response | WAV audio file |
| Health check | `curl -s http://192.168.5.150:9200/health` |
| Synthesis latency | ~500-600ms |

## The Working Pattern

macOS must do both the HTTP fetch and the playback. Binary pipes and FUSE mounts don't work with `afplay`.

```bash
mac bash -c 'curl -s -X POST http://192.168.5.150:9200/tts \
  -H "Content-Type: application/json" \
  -d "{\"text\":\"Your text here\"}" \
  --output "$TMPDIR/tts.wav" && afplay "$TMPDIR/tts.wav"'
```

### With timing

```bash
mac bash -c 'start=$(python3 -c "import time;print(int(time.time()*1000))"); \
  curl -s -X POST http://192.168.5.150:9200/tts \
  -H "Content-Type: application/json" \
  -d "{\"text\":\"Your text here\"}" \
  --output "$TMPDIR/tts.wav"; \
  fetched=$(python3 -c "import time;print(int(time.time()*1000))"); \
  echo "TTS fetch: $((fetched - start))ms"; \
  afplay "$TMPDIR/tts.wav"'
```

## What Does NOT Work

- `mac afplay <linux-path>` -- FUSE mount causes `AudioFileOpen failed ('wht?')`
- Piping WAV via stdin through `mac bash -c 'cat > ...'` -- arrives as 0 bytes
- `afplay` from Linux directly -- no audio devices in OrbStack VM

## Optional Parameters

```json
{"text": "Hello", "rate": 150, "volume": 0.8, "voice_id": "..."}
```

## Service Docs

Full TTS service code and architecture: `voice-edge/tts_service.py`, `voice-edge/ARCHITECTURE.md`
