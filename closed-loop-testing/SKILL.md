---
name: closed-loop-testing
description: Use when developing, deploying, or testing voice-edge changes end-to-end — covers the full cycle from code changes through deployment, audio testing, and metrics evaluation on the Pi voice assistant.
---

# Full E2E Development & Testing Cycle

## Overview

Complete development loop for the TARS voice pipeline: code -> test locally -> commit -> push -> deploy -> verify health -> test (API or audio) -> evaluate metrics -> iterate. Spans three hosts: Pi (knives-edge), 4090 GPU (STT/TTS), and Mac (mic recording + audio playback).

## When to Use

- After making code changes to rasp/, deploy/, or config files
- Verifying intent routing, timer/alarm behavior, wake word detection
- Running closed-loop audio tests end-to-end
- Deploying changes to the Pi and confirming they work
- Debugging failures in the voice pipeline

## Prerequisites & Setup Verification

### 1. Source Environment

**NEVER read `.env` directly** -- contents leak into session logs.

```bash
source /Users/aleiby/openclaw/.env 2>/dev/null
```

### 2. Mac Mic Service

Only needed once per Mac reboot. Must launch from Terminal.app (TCC mic permission):

```bash
set -a && source ~/openclaw/.env && set +a && python3 ~/mac_mic_service.py
```

Grant Terminal.app microphone permission in System Settings > Privacy & Security > Microphone if prompted.

### 3. Verify All Services

```bash
source /Users/aleiby/openclaw/.env 2>/dev/null

# Pi management service (no auth)
curl -s http://knives-edge.local:9300/health | python3 -m json.tool

# 4090 STT
curl -s http://192.168.5.150:9100/health

# 4090 TTS
curl -s http://192.168.5.150:9200/health

# Mac mic
curl -s http://aarons-macbook-pro.local:9400/health
```

Pi `/health` returns: `{"status": "ok", "cpu_temp_c": N, "throttled": bool, "services": {...}}`

The `services` field shows systemd active state of peer services (audio, rasp).

## Development Cycle

### Step 1: Make Code Changes

Edit files in `rasp/src/`, `deploy/`, `rasp_config.yaml`, etc.

### Step 2: Run Tests Locally

```bash
pytest tests/rasp/static/ -v
```

Static tests validate contracts, message schemas, and unit behavior without requiring live services.

### Step 3: Commit & Push

```bash
git add <files> && git commit -m "description" && git push
```

### Step 4: Deploy to Pi

```bash
source /Users/aleiby/openclaw/.env 2>/dev/null
curl -s -X POST http://knives-edge.local:9300/deploy \
  -H "X-Edge-Key: $EDGE_API_KEY" | python3 -m json.tool
```

The deploy endpoint performs `git pull` and auto-detects which services need restarting based on changed file paths:

| Changed path prefix | Services restarted |
|---------------------|--------------------|
| `deploy/` | knives-edge-mgmt only |
| `rasp/src/audio_service/` | knives-edge-audio |
| `rasp/src/mgmt_service/` | knives-edge-mgmt |
| `rasp/src/entrypoints/` | knives-edge-rasp |
| `rasp/src/core/` (shared) | knives-edge-audio + knives-edge-rasp |
| `rasp_config*` | all three services |
| unknown files | all three services (safety) |

Restart order is canonical: audio first, then rasp, then mgmt last (mgmt restart kills the handler process, so response is sent before restart begins).

Response includes `restart` (list of units) and `restart_reason` (why those units were chosen).

### Step 5: Verify Health Post-Deploy

Wait ~5-10 seconds for services to come back, then:

```bash
curl -s http://knives-edge.local:9300/health | python3 -m json.tool
```

Confirm `"status": "ok"` and all peer services are active.

### Step 6: Test

Choose the appropriate test pattern:

#### 6a. API-Only Intent Test (Fast, No Audio)

> **Legacy only -- not available in current rasp architecture.** The `POST /intent` endpoint existed on the legacy `pi/knives_edge.py` service. The current rasp mgmt service (port 9300) does not expose this endpoint. Use the full audio loop (6b) for intent testing instead.

For testing intent routing without the full audio chain (legacy service only):

```bash
source /Users/aleiby/openclaw/.env 2>/dev/null
curl -s -X POST http://knives-edge.local:9300/intent \
  -H "Content-Type: application/json" \
  -H "X-Edge-Key: $EDGE_API_KEY" \
  -d '{"text": "set a ten second timer"}'
```

#### 6b. Full Audio Loop

Record Mac mic while playing a wake command through TTS. Pi picks up wake word, processes intent, responds. Mac mic captures response. STT transcribes.

```bash
source /Users/aleiby/openclaw/.env 2>/dev/null

# 1. Start recording in background (15-20s for simple queries)
curl -s -X POST "http://aarons-macbook-pro.local:9400/record" \
  -H "X-Api-Key: $EDGE_API_KEY" -H "Content-Type: application/json" \
  -d '{"duration": 20}' --output /tmp/loop_test.wav &
sleep 2

# 2. Play wake command through Mac speakers
mac bash -c 'curl -s -X POST http://192.168.5.150:9200/tts \
  -H "Content-Type: application/json" \
  -d "{\"text\":\"Hey Jarvis, what time is it?\"}" \
  --output "$TMPDIR/tts.wav" && afplay "$TMPDIR/tts.wav"'

# 3. Wait for recording to finish
wait

# 4. Transcribe captured audio
curl -s -X POST http://192.168.5.150:9100/stt \
  -F "audio=@/tmp/loop_test.wav" \
  -F "prompt=Voice assistant response"
```

#### 6c. Timer/Alarm Verification

Set a short timer, record the alarm + announcement, verify via STT.

```bash
source /Users/aleiby/openclaw/.env 2>/dev/null

# 1. Start recording (25-30s for timer tests)
curl -s -X POST "http://aarons-macbook-pro.local:9400/record" \
  -H "X-Api-Key: $EDGE_API_KEY" -H "Content-Type: application/json" \
  -d '{"duration": 25}' --output /tmp/alarm_test.wav &
sleep 1

# 2. Set a short timer via API (legacy /intent endpoint only -- see 6a note)
curl -s -X POST http://knives-edge.local:9300/intent \
  -H "Content-Type: application/json" \
  -H "X-Edge-Key: $EDGE_API_KEY" \
  -d '{"text": "set a ten second timer"}'

# 3. Wait for recording
wait

# 4. Transcribe
curl -s -X POST http://192.168.5.150:9100/stt \
  -F "audio=@/tmp/alarm_test.wav" \
  -F "prompt=Timer alarm announcement"

# 5. CRITICAL: Stop the timer so alarm doesn't repeat forever
#    (legacy /intent endpoint only -- see 6a note)
curl -s -X POST http://knives-edge.local:9300/intent \
  -H "Content-Type: application/json" \
  -H "X-Edge-Key: $EDGE_API_KEY" \
  -d '{"text": "stop"}'
```

### Step 7: Evaluate

#### Read Metrics

```bash
source /Users/aleiby/openclaw/.env 2>/dev/null

# Legacy only -- these endpoints are NOT available in current rasp architecture.
# They existed on the legacy pi/knives_edge.py service.
#
# # Wake metrics (did the Pi detect "Hey Jarvis"?)
# curl -s "http://knives-edge.local:9300/metrics/wake?limit=5" \
#   -H "X-Edge-Key: $EDGE_API_KEY" | python3 -m json.tool
#
# # Intent metrics (what did it route to?)
# curl -s "http://knives-edge.local:9300/metrics/intent?limit=5" \
#   -H "X-Edge-Key: $EDGE_API_KEY" | python3 -m json.tool

# STT recent requests (on 4090)
curl -s "http://192.168.5.150:9100/metrics/recent?limit=5" | python3 -m json.tool

# TTS recent requests (on 4090)
curl -s "http://192.168.5.150:9200/metrics/recent?limit=5" | python3 -m json.tool
```

STT/TTS metrics support `event` filter (e.g., `?event=stt_req_ok&limit=5`).

#### Interpret Audio Levels

Mac mic recording returns `X-Mean-Volume` and `X-Max-Volume` headers:
- **-91 dB** = silence (no audio captured)
- **-30 to -10 dB** = normal speech levels
- If volume is near silence, check that speakers are on and mic is picking up audio

#### Check STT Results

STT returns JSON: `{"ok": true, "text": "...", "decode_ms": N}`

STT cannot distinguish non-speech audio (alarm.wav, chime.wav) -- it only transcribes spoken words.

### Step 8: Iterate

Fix issues, return to Step 1.

## Timing & Wait Guidance

| Operation | Expected Duration |
|-----------|-------------------|
| TTS synthesis | ~500-600ms |
| `sleep` after starting background recording | 2s (ensures mic is ready) |
| Recording duration: simple queries | 15-20s |
| Recording duration: timer/alarm tests | 25-30s |
| Deploy service restart | ~5-10s for services to come back |
| Pi wake word detection after audio plays | ~1-2s |

## Troubleshooting

| Problem | Check |
|---------|-------|
| Deploy hangs or fails | Read `restart_reason` in response; check if mgmt service restarted itself |
| No wake detection | Wake threshold (0.78), speaker volume, mic proximity |
| STT returns silence | Check `X-Mean-Volume` header from Mac mic recording |
| Chime not playing | Verify wav files exist in `/usr/share/rasp/chimes/` on Pi |
| Mac mic 403 | Ensure `X-Api-Key` header (not `X-Edge-Key`) |
| TTS playback fails | Must use `mac bash -c '...'` pattern; FUSE/pipes don't work with afplay |
| Services not restarting | Deploy auto-detects by file path; use explicit restart body if needed |
| No audio output from Pi | Check USB: `mac bash -c 'ssh knives-edge.local "dmesg \| grep -i usb \| tail -10"'`. If USB disconnect/reconnect, restart PipeWire (udev rule should handle automatically) |

## Pi SSH Access

SSH to the Pi is available via macOS bridge:

```bash
mac bash -c 'ssh knives-edge.local "command here"'
```

Useful for:
- Checking service logs: `journalctl -u knives-edge-rasp --since "5 min ago" --no-pager`
- Checking audio service logs: `journalctl -u knives-edge-audio --since "5 min ago" --no-pager`
- Restarting services: `sudo systemctl restart knives-edge-audio knives-edge-rasp`
- Testing audio directly: `paplay /usr/share/rasp/chimes/ready.wav`
- Checking USB/dmesg: `dmesg | tail -20`
- PulseAudio status: `pactl list sinks short`

## Related Skills

- **voice-edge-services**: Service map, endpoints, auth headers, volume control
- **tts-playback**: TTS fetch + macOS playback pattern, timing measurement

## Critical Reminders

- **ALWAYS stop timers after testing.** Ringing timers repeat the alarm indefinitely.
- **NEVER read `.env` directly.** Source and interpolate to keep secrets out of logs.
- **Use `mac bash -c '...'`** for macOS commands from OrbStack Linux VM.
- Wake word is **"Hey Jarvis"** (model: `hey_jarvis`, threshold: 0.78).
- Recording duration must be long enough to capture the full response chain.
- Post-deploy health check confirms services restarted successfully.
