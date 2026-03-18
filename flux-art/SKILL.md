---
name: flux-art
description: |
  Flux image generation for concept art and screenshot restyling.
  Uses FLUX.2 Pro (fal.ai API) or local inference (Klein 4B / Dev on RTX 4090).
  FLUX.1 Control LoRA Canny for structure-preserving transforms.

  INVOKE THIS SKILL when user requests Flux-specific image work:
  - "flux art", "generate with flux", "flux concept art"
  - "restyle this screenshot", "beautify this screenshot"
  - "concept art of...", "dieselpunk illustration of..."
user-invocable: true
---

# Flux Art — Concept Art Generation & Screenshot Restyling

## Quick Reference

```
/flux-art <request>              Generate concept art or restyle a screenshot
/flux-art --restyle <screenshot> Restyle a screenshot as concept art
/flux-art --fast <request>       Quick iteration with Klein (sub-second)
/flux-art --gallery              Start the gallery server (shared with nano-image)
/flux-art --help                 Show this help
```

## Environment

Requires a fal.ai API key. The scripts check in order:
1. `FAL_KEY` env var
2. `.env` in current directory, `~/.env`

Get a key at https://fal.ai/dashboard/keys

```bash
pip install fal-client
export FAL_KEY="your-key"
```

## Gallery

Shares the nano-image gallery at **http://localhost:8899**. All output goes to
`./nano-image-output/` with `.meta.json` sidecars tagged `model_tier: "flux"`.

Start the gallery (if not already running):
```bash
python3 ~/.claude/skills/nano-image/scripts/gallery_server.py \
  --port 8899 \
  --dir ./nano-image-output &
```

## Output Directory

All generated images go to `./nano-image-output/` relative to the current working
directory by default. Pass `--output-dir` to scripts to override. Pass `--output`
for a specific file location.

## Step 1: Classify the Request

Every request falls into one of three modes:

| Mode | When | Script | Endpoint |
|------|------|--------|----------|
| `concept` | New art from text prompt | generate.py | FLUX.2 Pro |
| `refine` | Iterate on previous output | generate.py --input | FLUX.2 Pro Edit |
| `restyle` | Structure-preserving screenshot beautification | restyle.py | FLUX.1 Control LoRA Canny |

Classify the request BEFORE doing anything else.

### Model Tiers (generate.py --tier)

| Tier | Endpoint | Cost | When |
|------|----------|------|------|
| `pro` (default) | `fal-ai/flux-2-pro` | $0.03/MP | Final quality, best prompt adherence |
| `fast` | `fal-ai/flux-2/klein/4b/distilled` | $0.009/MP | Exploration, sub-second, iteration |
| `dev` | `fal-ai/flux-2/edit` | $0.012/MP | Full parameter control (guidance, steps, num_images) |

Use `--tier fast` when brainstorming or exploring. Use `--tier pro` for final output.
The `dev` tier is for when you need `--guidance-scale`, `--num-inference-steps`, or
`--num-images` (Pro and Klein are zero-config).

## Step 2: Build the Prompt

**CRITICAL: Flux uses positive-only prompting.** Describe what you want to see.
Never describe what to avoid. Flux may interpret negated words literally — "no blur"
can trigger blur. Instead of "no blur", say "sharp crisp details".

Flux also understands:
- **Hex color codes** directly in prompts (e.g., "sky in #1a2b4f deep navy")
- Detailed scene descriptions with specific artistic vocabulary

Build a structured spec, then convert to a rich narrative prompt:

```json
{
  "mode": "concept|refine|restyle",
  "prompt": "detailed scene description using positive-only language",
  "input_image": "path if refine/restyle mode",
  "image_size": "landscape_16_9",
  "tier": "pro|fast|dev",
  "label": "descriptive-filename-prefix"
}
```

### Image Size

The `--image-size` parameter accepts:
- **Preset names**: `square_hd`, `square`, `portrait_4_3`, `portrait_16_9`, `landscape_4_3`, `landscape_16_9`
- **Aspect ratio aliases**: `16:9`, `4:3`, `1:1`, `9:16`, `3:4` (auto-mapped to presets)
- **Custom dimensions**: `1920x1080` (WxH format)

Default: `landscape_4_3`

### Applying Presets

Check if a preset applies:
- **In signal-line project context**: auto-apply `signal_line.json` preset — merge
  its style keywords and palette hex codes into the prompt
- **Generic concept art**: use `concept_art.json` defaults

Presets provide style vocabulary and palette hex codes to weave into the prompt.
They use positive-only language.

### Applying Templates

Load the appropriate template for sensible parameter defaults:
- `concept.json` — new concept art generation
- `screenshot_restyle.json` — screenshot beautification

## Step 3: Generate

### Concept mode (new art from text)
```bash
python3 ~/.claude/skills/flux-art/scripts/generate.py \
  --prompt "detailed scene description" \
  --image-size "16:9" \
  --output-dir ./nano-image-output \
  --label "concept-train"
```

### Fast exploration (Klein, sub-second)
```bash
python3 ~/.claude/skills/flux-art/scripts/generate.py \
  --prompt "detailed scene description" \
  --tier fast \
  --image-size "16:9" \
  --output-dir ./nano-image-output \
  --label "explore-train"
```

### Refine mode (iterate on existing image)
```bash
python3 ~/.claude/skills/flux-art/scripts/generate.py \
  --prompt "editing instructions" \
  --input /path/to/previous-output.png \
  --output-dir ./nano-image-output \
  --label "refine-train"
```

### Restyle mode (screenshot → concept art)
```bash
python3 ~/.claude/skills/flux-art/scripts/restyle.py \
  --prompt "painterly dieselpunk concept art, dramatic volumetric lighting" \
  --input /path/to/screenshot.png \
  --output-dir ./nano-image-output \
  --label "restyle-scene"
```

## Step 4: Review the Output

After generation, READ the output image file to inspect it visually.

Load the rubric from `~/.claude/skills/flux-art/rubrics/game_art_review.md` and score:

1. **Aesthetic quality** — Does it read as polished concept art?
2. **Style coherence** — Does it match the requested aesthetic?
3. **Composition** — Is the layout effective and balanced?
4. **Lighting & atmosphere** — Are light sources dramatic and purposeful?
5. **Structure preservation** (restyle only) — Does it maintain the original composition?
6. **Prompt adherence** — Does it match what was requested?

Rate: ACCEPT / RETRY / FAIL

## Step 5: Retry or Accept

### Retry strategy:
- Up to **3 retries** with revised prompt
- Each retry should tighten the prompt — add specificity, strengthen style keywords
- If using `--tier fast`, consider escalating to `--tier pro` for final attempt
- After 3 retries, present best result and ask user

### How to retry:
1. Identify what went wrong from the rubric
2. Revise the prompt — add stronger positive descriptors
3. Adjust parameters (image_size, tier)
4. Regenerate

**Remember: positive-only revisions.** If the result was too dark, say "bright
ambient fill light, well-lit scene" — not "not dark".

## Step 6: Present Result

Tell the user the image is in the gallery (http://localhost:8899). If the gallery
isn't running, mention the output file path.

Mention:
- Brief description of what was generated
- Model tier used and cost
- If you iterated, what was adjusted

Do NOT show raw JSON specs or technical details unless asked.

## Revision Workflow

When the user asks to revise an existing image:

1. Load the `.meta.json` sidecar from the previous output
2. Build a delta — only change the fields that need updating
3. Carry forward the original prompt's style and detail
4. For edits to an existing image, use `generate.py` with `--input` pointing to the
   previous output
5. For regeneration with a modified prompt, use `generate.py` without `--input`

## Local Inference (GPU Server)

Instead of the fal.ai API, you can run FLUX.2 on a local GPU (e.g., RTX 4090).
The `serve.py` script runs a lightweight inference server that the client scripts
call over the network.

### Setup (on the GPU machine)

```bash
# Install dependencies
pip install torch torchvision --index-url https://download.pytorch.org/whl/cu124
pip install diffusers transformers accelerate sentencepiece protobuf
pip install fastapi uvicorn pillow

# Start server (Klein 4B preloaded — 8.4GB VRAM, sub-second generation)
python3 ~/.claude/skills/flux-art/scripts/serve.py --port 8190
```

### Client configuration

Set `FLUX_LOCAL_URL` on the machine running the flux-art scripts:

```bash
export FLUX_LOCAL_URL=http://192.168.1.100:8190   # your GPU machine's IP
```

Or add to `.env`:
```
FLUX_LOCAL_URL=http://192.168.1.100:8190
```

When `FLUX_LOCAL_URL` is set, all generate.py calls route to the local server.
When unset, they fall back to the fal.ai API.

### Local tier mapping

| --tier | Local model | VRAM | Speed (1024x1024) |
|--------|-------------|------|-------------------|
| `fast` | Klein 4B distilled | ~8.4 GB | ~1 second |
| `dev` | Dev 32B (FP8) | ~18 GB | ~5-7 seconds |
| `pro` | Maps to dev locally | ~18 GB | ~5-7 seconds |

Pro is API-only. When `FLUX_LOCAL_URL` is set and `--tier pro` is requested, the
local server uses dev as the closest equivalent. For true Pro quality, unset
`FLUX_LOCAL_URL` and use the fal.ai API.

### Health check

```bash
curl http://192.168.1.100:8190/health
```

## Pricing

### fal.ai API

| Tier | Endpoint | Cost |
|------|----------|------|
| Pro | `fal-ai/flux-2-pro` | ~$0.03/megapixel |
| Fast (Klein) | `fal-ai/flux-2/klein/4b/distilled` | ~$0.009/megapixel |
| Dev | `fal-ai/flux-2/edit` | ~$0.012/megapixel |
| Restyle (Canny) | `fal-ai/flux-control-lora-canny` | ~$0.04/megapixel |

### Local inference

Effectively free (electricity only). Klein 4B: ~50-60 images/minute on RTX 4090.
