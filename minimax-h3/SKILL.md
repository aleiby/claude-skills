---
name: minimax-h3
description: Use when generating video with MiniMax H3 or H3 Ref2VA over the private LAN, including uploading references, submitting cached line jobs, resuming handles, or downloading native video and masks.
---

# MiniMax H3 Ref2VA

Use the bundled zero-dependency Python client. Do not invent routes, job IDs,
cache keys, upload IDs, signed URLs, or cache-busting nonces.

```bash
SKILL_DIR="$HOME/.claude/skills/minimax-h3"
CLIENT="$SKILL_DIR/scripts/minimax_h3_client.py"
python3 "$CLIENT" --help
```

## Configuration

The client reads, in order:

1. `MINIMAX_H3_API` and `MINIMAX_H3_TOKEN`
2. `~/.config/minimax-h3/config.json`
3. unauthenticated `http://127.0.0.1:8191`

Never put a token on the command line or print it. JSON config files containing a
token must be mode `0600` on Unix. A config looks like:

```json
{"api": "http://192.168.5.150:8191", "token": "REDACTED"}
```

The MiniMax names and config path are the complete supported surface. Do not
look for or create project-specific aliases.

## Required workflow

At the start of a generation batch, verify the endpoint and fetch its
authoritative model surface:

```bash
python3 "$CLIENT" doctor
python3 "$CLIENT" schema > /tmp/minimax-h3-schema.json
```

Reject an incompatible protocol instead of guessing. The client supports
protocol major 1. Treat schema defaults, installed model choices, ranges, and
frame limits as authoritative.

Copy the template into the working directory and edit it. Keep `local_inputs`
in semantic order: `<Picture 1>` maps to the first image, `<Video 1>` to the
first video, and `<Audio 1>` to the first standalone audio.

```bash
test ! -e ./h3-submission.json || { echo "h3-submission.json already exists" >&2; exit 1; }
cp -f "$SKILL_DIR/templates/submission.json" ./h3-submission.json
python3 "$CLIENT" submit ./h3-submission.json | tee ./h3-submission-result.json
```

The client hashes each local file, reuses uploaded blobs by digest, converts
`local_inputs` to the exact `inputs` contract, and defaults `cache_policy` to
`use`. Record the returned `handle_id` and `attempt_id` immediately. A
disconnect does not cancel the work.

Wait on the durable handle; the default polling interval is 20 seconds:

```bash
python3 "$CLIENT" wait HANDLE_ID | tee ./h3-final.json
```

On success, download the native H3 MP4 and optional mask using the artifact
metadata attached to that handle:

```bash
python3 "$CLIENT" download HANDLE_ID video ./line.mp4
python3 "$CLIENT" download HANDLE_ID mask ./line-mask.mkv
```

Downloads stage to `.part`, verify the advertised byte count, SHA-256, and
ETag, fsync, then rename atomically. The MP4's picture and native synchronized
audio must stay together. The mask is grayscale FFV1 in Matroska.

## Cache and recovery

- Use the default `cache_policy: "use"` for ordinary line submissions. Identical
  creative inputs join active work or reuse a successful result.
- Use `--refresh` only when the user explicitly invalidates a result or an exact
  rerender is required despite a successful cached attempt.
- Never add a nonce or compute a cache key. The server owns render identity.
- Resume with `status HANDLE_ID` or `wait HANDLE_ID`; do not resubmit merely
  because the client session ended.
- Cancel only with `cancel HANDLE_ID`. Cancellation drops that handle's
  interest and may not stop shared work another handle still wants.

## Quick reference

| Goal | Command |
| --- | --- |
| Validate service | `python3 "$CLIENT" doctor` |
| Inspect live controls | `python3 "$CLIENT" schema` |
| Upload one file | `python3 "$CLIENT" upload PATH` |
| Submit/reuse | `python3 "$CLIENT" submit MANIFEST.json` |
| Explicit replacement | `python3 "$CLIENT" submit MANIFEST.json --refresh` |
| Inspect handle | `python3 "$CLIENT" status HANDLE_ID` |
| Wait to terminal state | `python3 "$CLIENT" wait HANDLE_ID` |
| Cancel interest | `python3 "$CLIENT" cancel HANDLE_ID` |
| Fetch verified output | `python3 "$CLIENT" download HANDLE_ID video OUTPUT.mp4` |

## Common mistakes

- Do not call ComfyUI directly; it is localhost-only and is not the public API.
- Do not send host filesystem paths to the service. Use `local_inputs`; the
  client uploads bytes and substitutes `sha256:` blob IDs.
- Do not reorder references after writing numbered prompt tokens.
- Do not discard or replace H3's output soundtrack during assembly.
- Do not assume a remembered frame cap or model filename; read `schema`.
- Do not treat `attempt_id` as the caller resume token; persist `handle_id`.
- Do not use offset framing without an actual plate during episode assembly;
  this service only generates the line assets.

For the exact route and manifest contract, read [references/api.md](references/api.md).
