# MiniMax H3 service contract

Port: `8191`. All routes except `GET /health/live` require
`Authorization: Bearer <token>`.

## Routes

| Method and path | Meaning |
| --- | --- |
| `GET /health/live` | Unauthenticated process liveness |
| `GET /health/ready` | Authenticated runtime/model/queue readiness |
| `GET /v1/h3/schema` | Protocol version and complete approved Ref2VA surface |
| `HEAD /v1/blobs/{hex_sha256}` | Test immutable input existence |
| `GET /v1/blobs/{hex_sha256}` | Download immutable input bytes |
| `POST /v1/blobs` | Upload one digest-verified input |
| `POST /v1/h3/submissions` | Submit, join, refresh, or reuse work |
| `GET /v1/h3/submissions/{handle_id}` | Caller-visible durable state |
| `POST /v1/h3/submissions/{handle_id}/cancel` | Cancel this handle's interest |
| `GET /v1/h3/attempts/{attempt_id}` | Shared attempt state |
| `GET /v1/artifacts/{artifact_id}` | Download a validated immutable artifact |

ComfyUI on port 8190 is an implementation detail and not a client surface.

## Blob upload

Hash the complete file with lowercase SHA-256. First issue
`HEAD /v1/blobs/{hex_sha256}`. For a missing blob:

```text
POST /v1/blobs
X-Blob-Sha256: sha256:<hex_sha256>
Content-Length: <bytes>
Content-Type: <media-type>

<raw file bytes>
```

A new upload returns 201; verified deduplication is idempotent. Retry an
interrupted upload from byte zero.

## Submission JSON

The public top-level fields are exactly:

- `labels`: optional string metadata, excluded from render identity
- `prompt`: exact prompt; the server does not enhance it
- `inputs`: ordered `reference_images`, paired `reference_videos`, and
  standalone `reference_audios`, all using `sha256:` blob IDs
- `generation`: width, height, length, reference image sizing, seed, sampler,
  scheduler, steps, denoise
- `models`: video/audio VAEs, text encoder/type/device, diffusion model, dtype
- `output`: fps, bit depth, format, codec, encoding controls
- `mask`: `enabled`
- `cache_policy`: `use` or `refresh`

The bundled client additionally accepts local-only `local_inputs` with the same
three ordered arrays and replaces it with uploaded blob IDs before submission.
It never sends `local_inputs` to the server.

Unknown server fields, invalid nulls, duplicate JSON keys, non-finite numbers,
unavailable choices, and out-of-range values are rejected. Read schema for the
live defaults and allowed surface. The frame grid begins at 5 and advances by
17, but the installed maximum is schema-owned.

`reference_videos` entries have this shape:

```json
{"video": "sha256:<digest>", "audio": "sha256:<digest>"}
```

The paired audio may be omitted. Standalone dialogue or other audio references
belong in `reference_audios`.

## Identity, state, and artifacts

The submission response includes `handle_id`, `attempt_id`, deterministic
`content_key`, current `state`, join/cache flags, effective manifest, and any
artifacts. Persist `handle_id` for caller recovery.

Attempt phases are:

```text
queued -> submitting -> generating -> masking -> validating -> publishing
       -> succeeded | failed | cancelled
```

`cache_policy: "use"` joins or reuses matching work. `refresh` creates or joins
one replacement while the prior successful result remains active until the new
one publishes. No client nonce or client cache key exists.

A successful masked result contains one native MP4 `video` and one grayscale
FFV1 Matroska `mask` from the same attempt. Artifact documents advertise
`artifact_id`, `url`, `size`, `sha256`, `etag`, media type, and attempt ID.
Verify all advertised integrity values before publishing a local download.
