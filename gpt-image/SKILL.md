---
name: gpt-image
description: |
  Image generation and editing via OpenAI's gpt-image-2, routed through the
  Codex CLI to use the user's ChatGPT Pro subscription billing instead of
  pay-per-image API charges.

  INVOKE THIS SKILL when the user requests image work and explicitly mentions
  OpenAI / gpt-image / ChatGPT image generation, OR for asset/sprite generation
  workflows where the user wants Pro subscription billing:
  - "gpt-image", "openai image", "chatgpt image"
  - "generate a sprite", "make an asset", "alpha texture"
  - "generate this with gpt-image-2"

  For Flux-specific work, use flux-art instead.
  For Gemini/Nano Banana work, use nano-image instead.
user-invocable: true
---

# GPT Image — Codex CLI–routed gpt-image-2

OpenAI's `gpt-image-2` (released April 2026), invoked through the Codex CLI's
built-in `$imagegen` skill so usage counts against the user's ChatGPT Pro
subscription instead of pay-per-image API billing.

## Quick Reference

```
/gpt-image <request>                 Generate an image
/gpt-image --input <ref.png> <req>   Edit / extend a reference image
/gpt-image --gallery                 Start the gallery server (shared)
/gpt-image --help                    Show this help
```

## Auth

Uses the Codex CLI's existing login. No separate `OPENAI_API_KEY` required —
billing flows through the user's ChatGPT plan. If `OPENAI_API_KEY` is set in
the environment, Codex switches to API billing automatically.

Image generation counts against ChatGPT plan usage **3-5× faster** than
text-only Codex turns. For large batches, set `OPENAI_API_KEY` to switch to
API pricing instead.

## Gallery

Shares the nano-image gallery at **http://localhost:8899**. All output goes to
`./nano-image-output/`. Start the gallery (if not already running):

```bash
python3 ~/.claude/skills/nano-image/scripts/gallery_server.py \
  --port 8899 \
  --dir ./nano-image-output &
```

## Output Directory

Codex saves to `~/.codex/generated_images/`. Recent codex versions nest each
session's outputs in a UUID subdirectory, so `generate.py` walks the tree
recursively to find new image files, then **always moves them to
`./nano-image-output/`** (relative to cwd) so the shared gallery at :8899
picks them up.

`--output-dir <path>` no longer redirects the move — it requests an
additional **copy** at that path for project organization. The gallery copy
is the canonical home; the secondary copy is a duplicate. Both locations
also receive the `.meta.json` sidecar. This way every generated image is
reviewable in the gallery regardless of which project subdir the caller
wanted to organize it into.

## Step 1: Classify the Request

| Mode | When | Script | Notes |
|------|------|--------|-------|
| `concept` | New image from text prompt | generate.py | Text-to-image |
| `edit` | Modify a single reference image | generate.py --input X | Pass one reference |
| `compose` | Combine multiple references | generate.py --input A B C | Multiple refs |
| `iterate` | Refine a previous gpt-image output | generate.py --input prev.png | Same as edit, conceptually |

Classify before generating.

## Step 2: Build the Prompt

`gpt-image-2` is a multimodal language model with strong instruction-following
and contextual awareness. Prompts can be conversational and detailed.

Key prompt strategies:

- **Describe the scene narratively** — gpt-image-2 understands rich descriptions
  better than keyword lists.
- **Reference image semantics explicitly** when using `--input`. Example:
  "use the colour palette from image 1, the silhouette from image 2."
- **Specify text content verbatim** if any text must appear in the image.
  gpt-image-2 has strong text rendering.
- **Output filename can be embedded in the prompt** — Codex's $imagegen skill
  parses natural-language file directives (e.g., "save as weed_alpha.png").
  Otherwise the script auto-names from the `--label`.

### Sprite / asset prompts

For game-asset texture work, useful prompt patterns:

- "alpha-channel sprite of <subject>, transparent background, isolated, square
  framing, soft edges, no shadow on the ground"
- "tileable texture, <subject>, 1024×1024, looks seamless when tiled"
- "concept art reference of <subject>, painterly, on plain background"

Specify dimensions in the prompt: "1024×1024", "1536×1024 landscape", etc.
Codex CLI's $imagegen has known issues with deterministic output dimensions —
the prompt-level hint is more reliable than relying on flag-passing.

## Step 3: Generate

### Concept (text-to-image)
```bash
python3 ~/.claude/skills/gpt-image/scripts/generate.py \
  --prompt "alpha-channel sprite of a tall grass clump, transparent background, painterly" \
  --label "weed-alpha"
# → ./nano-image-output/weed-alpha-YYYYMMDD-HHMMSS.png  (gallery sees it)
```

### Edit / iterate (with reference image)
```bash
python3 ~/.claude/skills/gpt-image/scripts/generate.py \
  --prompt "make the colour deeper green and add slight motion blur on the tips" \
  --input ./assets/textures/grass_blade_alpha.png \
  --label "weed-edit"
```

### Compose (multiple references) + secondary copy for project organization
```bash
python3 ~/.claude/skills/gpt-image/scripts/generate.py \
  --prompt "combine the silhouette from image 1 with the painterly style from image 2" \
  --input ./refs/silhouette.png ./refs/style.png \
  --label "concept" \
  --output-dir ./concepts/whatever
# → primary:   ./nano-image-output/concept-...png  (gallery)
# → secondary: ./concepts/whatever/concept-...png  (project-organized copy)
```

The script:

1. Recursively snapshots image files under `~/.codex/generated_images/`
   (codex nests outputs in per-session UUID subdirs).
2. Calls `codex exec -s workspace-write [-i refs] "$imagegen <prompt>"` with
   stdin redirected to `/dev/null` (codex stdin gotcha).
3. Detects new image files anywhere in that tree.
4. Moves each new file into `./nano-image-output/` with the script's naming
   scheme (`<label>-YYYYMMDD-HHMMSS.png`) and writes a `.meta.json` sidecar.
5. If `--output-dir` was set and differs from `./nano-image-output`, also
   copies the image + sidecar there.

## Step 4: Review

After generation, READ the output image to inspect it. Score against:

1. **Subject accuracy** — is the main subject correct?
2. **Style adherence** — matches the requested aesthetic?
3. **Text correctness** — if text was requested, is it legible/accurate?
4. **Reference fidelity** (when using `--input`) — does the output respect the
   referenced silhouette / palette / composition?
5. **Asset suitability** — for game assets, is the alpha channel clean? Edges
   crisp? No unwanted background?
6. **Artifacts** — extra limbs, distortion, double-text, etc.?

Rate: PASS / RETRY / FAIL.

## Step 5: Retry

Up to 2 retries with revised prompts. Each retry should add specificity
(stronger style descriptors, explicit constraints, clearer reference
instructions) rather than reusing the same prompt.

For asset work, common fixes:
- "transparent background" → "fully transparent alpha, no white halo, no
  gray border"
- "no shadow" → "isolated subject, no cast shadow, no ground plane"
- Edge artifacts → "crisp anti-aliased edges, clean alpha cutout"

After 2 retries, present the best result and ask the user.

## Step 6: Present Result

Mention:
- Brief description of what was generated.
- Output path (under `./nano-image-output/`).
- Gallery URL if running.
- If iterated, what was adjusted between attempts.

Don't show raw spec JSON or technical details unless asked.

## Notes / Limitations

- **No batch parallelism** — Codex CLI serializes turns. For "give me 4 options",
  loop the script. Each call is a separate Codex turn against your plan.
- **No deterministic dimensions** — gpt-image-2 in Codex CLI has known issues
  delivering exactly the requested resolution. Specify dimensions in the prompt
  but be ready to crop/resize the output.
- **`gpt-image-2` model only** — no model tier knob. If you need speed/cost
  tradeoffs (gpt-image-1.5 / 1-mini), switch to direct API and set
  `OPENAI_API_KEY`; this skill will then bill per-call instead of plan-counted.
- **Reference images are passed as-is** — Codex sees them via the `-i` flag,
  attaches them to the first message, and the model decides how to use them.
  Be explicit in the prompt about which reference plays which role.
