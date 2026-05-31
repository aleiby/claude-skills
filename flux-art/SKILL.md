---
name: flux-art
description: |
  Flux image generation for concept art and screenshot restyling.
  Uses FLUX.2 via BFL API (Pro/Max/Kontext), local inference (Klein 4B on RTX 4090),
  mflux on Mac (Klein 4B/9B via MLX), or fal.ai as fallback.

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

### API Keys (checked in order)

**BFL API (recommended)** — direct from Black Forest Labs:
1. `BFL_API_KEY` env var
2. `.env` in current directory, `~/.env`

Get a key at https://dashboard.bfl.ai

**fal.ai (fallback)**:
1. `FAL_KEY` env var
2. `.env` in current directory, `~/.env`

### Local Server (RTX 4090)

Set `FLUX_LOCAL_URL` to route fast tier to the 4090:
```bash
export FLUX_LOCAL_URL=http://192.168.5.150:8190
```

### Local Mac (mflux / MLX)

Klein 4B/9B run natively on Apple Silicon via mflux:
```bash
uv tool install --python 3.12 mflux
mac bash -c 'source ~/.zshrc && mflux-generate-flux2 --model flux2-klein-4b ...'
```

Requires `HF_TOKEN` in `~/.zshrc` for gated models (Klein 9B, Dev).

## Backend Routing

generate.py auto-routes based on tier and available credentials:

| Tier | Auto route | Notes |
|------|-----------|-------|
| `fast` | Local server if `FLUX_LOCAL_URL` set, else BFL API, else fal.ai | Klein 4B, ~2s on 4090 |
| `dev` | BFL API (local 4090 OOMs with 32B) | 32B, ~15s via API |
| `pro` | BFL API if `BFL_API_KEY` set, else fal.ai | Production quality |
| `max` | BFL API only | Highest quality, best photorealism |
| `kontext-pro` | BFL API | Targeted local edits (limited effectiveness) |
| `kontext-max` | BFL API | Better prompt adherence for edits |

Override with `--backend local|bfl|fal` to force a specific backend.

## Gallery

Shares the nano-image gallery at **http://localhost:8899**. All output goes to
`./nano-image-output/`. The gallery reads metadata from:
1. `.meta.json` sidecar files (flux-art generate.py output)
2. Embedded PNG metadata (mflux EXIF UserComment — automatic, no sidecar needed)

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

Every request falls into one of four modes:

| Mode | When | Script | Notes |
|------|------|--------|-------|
| `concept` | New art from text prompt | generate.py | Text-to-image |
| `refine` | Iterate on previous output | generate.py --input | Single image edit |
| `composite` | Combine elements from multiple images | generate.py --input img1 img2 ... | Multi-reference (up to 4 Klein, 8 Pro/Max) |
| `restyle` | Structure-preserving screenshot beautification | restyle.py | FLUX.1 Control LoRA Canny |

**Compositing limitations**: Multi-reference character compositing is unreliable
across all FLUX models. Characters from reference sheets are often ignored or
poorly integrated. Best approach: describe all characters in the text prompt
from scratch, or use Nano Banana (Gemini) for targeted edits like fixing details.

Classify the request BEFORE doing anything else.

### Model Tiers (generate.py --tier)

| Tier | Quality | Cost (BFL) | When |
|------|---------|-----------|------|
| `max` | Best | ~$0.04-0.06/MP | Final hero images, best prompt adherence |
| `pro` (default) | High | ~$0.03/MP | Production quality, good prompt adherence |
| `dev` | Good | ~$0.012/MP | Full parameter control (guidance, steps, num_images) |
| `fast` | Draft | ~$0.014/MP or free local | Exploration, iteration, batch generation |
| `kontext-pro` | Targeted edits | varies | Local edits to specific elements |
| `kontext-max` | Better targeted edits | varies | Better prompt adherence for edits |

Use `--tier fast` when brainstorming or exploring. Use `--tier max` for final output.

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
  "mode": "concept|refine|composite|restyle",
  "prompt": "detailed scene description using positive-only language",
  "input_images": ["path1.png", "path2.png"],
  "image_size": "landscape_16_9",
  "tier": "max|pro|fast|dev|kontext-pro|kontext-max",
  "backend": "auto|local|bfl|fal",
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

### Fast exploration (Klein, ~2s on 4090)
```bash
python3 ~/.claude/skills/flux-art/scripts/generate.py \
  --prompt "detailed scene description" \
  --tier fast \
  --image-size "16:9" \
  --output-dir ./nano-image-output \
  --label "explore-train"
```

### Max quality (BFL API)
```bash
python3 ~/.claude/skills/flux-art/scripts/generate.py \
  --prompt "detailed scene description" \
  --tier max \
  --image-size "16:9" \
  --output-dir ./nano-image-output \
  --label "hero-train"
```

### Refine mode (iterate on existing image)
```bash
python3 ~/.claude/skills/flux-art/scripts/generate.py \
  --prompt "editing instructions" \
  --input /path/to/previous-output.png \
  --output-dir ./nano-image-output \
  --label "refine-train"
```

### Multi-reference composite (combine elements from multiple images)
```bash
python3 ~/.claude/skills/flux-art/scripts/generate.py \
  --prompt "combine the locomotive from image 1 with the tunnel lighting from image 2" \
  --input /path/to/train.png /path/to/tunnel.png \
  --tier fast \
  --output-dir ./nano-image-output \
  --label "composite-train"
```

Klein supports up to 4 input images, Pro/Max up to 8.

### Targeted edits with Kontext
```bash
python3 ~/.claude/skills/flux-art/scripts/generate.py \
  --prompt "Change the character's coat from brown to green" \
  --input /path/to/scene.png \
  --tier kontext-pro \
  --output-dir ./nano-image-output \
  --label "edit-coat"
```

Note: Kontext works best for simple color/texture changes. It struggles with
small elements, character additions/removals, and complex edits at low resolution.

### Force a specific backend
```bash
# Force BFL API even for fast tier (compare against local)
--backend bfl --tier fast

# Force local server
--backend local --tier fast
```

### Mac local generation (mflux / MLX)
```bash
mac bash -c 'source ~/.zshrc && mflux-generate-flux2 \
  --model flux2-klein-9b --quantize 8 \
  --prompt "detailed scene description" \
  --width 1024 --height 576 --steps 4 --guidance 1.0 \
  --output <ABS_PROJECT_PATH>/nano-image-output/my-image.png \
  --metadata'
```

mflux embeds full metadata in the PNG — the gallery reads it automatically.
Substitute the current project's absolute path for `<ABS_PROJECT_PATH>` (the
gallery lives at `<project>/nano-image-output/`). Use a Mac-absolute path (not
`~/` or a relative cwd) for `--output` — OrbStack can't translate those from the
Linux VM side.

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
- If using `--tier fast`, consider escalating to `--tier pro` or `--tier max` for final attempt
- After 3 retries, present best result and ask user

### How to retry:
1. Identify what went wrong from the rubric
2. Revise the prompt — add stronger positive descriptors
3. Adjust parameters (image_size, tier, backend)
4. Regenerate

**Remember: positive-only revisions.** If the result was too dark, say "bright
ambient fill light, well-lit scene" — not "not dark".

## Step 6: Present Result

Tell the user the image is in the gallery (http://localhost:8899). If the gallery
isn't running, mention the output file path.

Mention:
- Brief description of what was generated
- Model tier and backend used
- If you iterated, what was adjusted

Do NOT show raw JSON specs or technical details unless asked.

## Revision Workflow

When the user asks to revise an existing image:

1. Load the `.meta.json` sidecar from the previous output
2. Build a delta — only change the fields that need updating
3. Carry forward the original prompt's style and detail
4. For edits to an existing image, use `generate.py` with `--input` pointing to the
   previous output
5. For multi-reference compositing, use `--input img1.png img2.png` with a prompt
   describing which elements to take from each
6. For regeneration with a modified prompt, use `generate.py` without `--input`
7. For targeted edits (color changes, simple modifications), try Nano Banana (Gemini)
   which has better instruction-following for surgical changes

## Local Inference — RTX 4090 (serve.py)

The `serve.py` script runs a lightweight inference server on a GPU machine.

### Setup (on the GPU machine)

```bash
pip install torch torchvision --index-url https://download.pytorch.org/whl/cu124
pip install git+https://github.com/huggingface/diffusers.git
pip install transformers accelerate sentencepiece protobuf
pip install fastapi uvicorn pillow

python3 ~/.claude/skills/flux-art/scripts/serve.py --port 8190
```

**Important**: Requires latest diffusers from git for `Flux2KleinPipeline`.
Uses `Flux2Pipeline` for dev tier (NOT `FluxPipeline` which is FLUX.1).

### Pipeline classes
- Klein 4B: `Flux2KleinPipeline` (~15GB VRAM)
- Dev 32B: `Flux2Pipeline` — **does NOT work on 24GB cards** (OOMs even with CPU offload)

### Diagnostic endpoints

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/health` | GET | Server status and loaded models |
| `/gpu` | GET | VRAM usage (allocated/reserved/free) and process list |
| `/clear-cache` | POST | Reclaim fragmented VRAM via gc + empty_cache |
| `/unload?tier=fast` | POST | Unload a specific model to free memory |
| `/unload` | POST | Unload all models |

## Local Inference — Mac (mflux / MLX)

Klein 4B and 9B run natively on Apple Silicon via mflux (MLX).

### Setup

```bash
uv tool install --python 3.12 mflux
```

Requires `HF_TOKEN` in `~/.zshrc` for gated models.

### Supported models

| Model | Command | Quantize | Time (M4 Max 128GB) |
|-------|---------|----------|---------------------|
| Klein 4B | `mflux-generate-flux2 --model flux2-klein-4b` | 4 or 8 | ~7-8s |
| Klein 9B | `mflux-generate-flux2 --model flux2-klein-9b` | 8 | ~16s |
| Dev 32B | Not yet supported in mflux | — | — |

Use `--metadata` to embed generation info in the PNG (gallery reads it automatically).

### Important notes
- Use `mflux-generate-flux2` (not `mflux-generate` which is FLUX.1)
- Use absolute paths for `--output` (not `~/`)
- Run via `mac bash -c 'source ~/.zshrc && mflux-generate-flux2 ...'`

## Local Inference — Mac (flux-2-swift-mlx) — Dev 32B

Dev 32B runs on M4 Max 128GB via the Swift MLX implementation.

### Setup

```bash
# Clone and build (requires Xcode + Metal Toolchain)
git clone https://github.com/VincentGourbin/flux-2-swift-mlx.git
cd flux-2-swift-mlx
xcodebuild -downloadComponent MetalToolchain
xcodebuild -scheme Flux2CLI -configuration Release -destination "platform=macOS" build

# Download models
Flux2CLI download --model dev --transformer-quant int4
Flux2CLI download --model dev --transformer-quant qint8
```

**Important**: `swift build` does NOT compile Metal shaders. Must use `xcodebuild`.

Binary location: `~/Library/Developer/Xcode/DerivedData/flux-2-swift-mlx-*/Build/Products/Release/Flux2CLI`

### Usage

```bash
mac bash -c 'source ~/.zshrc && /path/to/Flux2CLI t2i \
  "prompt here" \
  --model dev --transformer-quant int4 \
  --width 1024 --height 576 --steps 28 \
  -o <ABS_PROJECT_PATH>/nano-image-output/output.png \
  --profile'
```

### Quantization options

| Quant | Per Step | Total (28 steps) | Memory | Notes |
|-------|----------|-------------------|--------|-------|
| int4 | ~25s | ~12-17min | ~32GB | Preferred for Signal Line concept art (more stylized/contrasty) |
| qint8 | ~28s | ~13min | ~64GB | More precise, use for text/fine detail |

First run downloads Mistral text encoder (~5min overhead, cached after).
Use `--upsample-prompt` to enhance prompts with more visual detail.
Does NOT embed metadata — create `.meta.json` sidecar manually.

## Performance Summary

| Backend | Model | Time (1024x576) | Cost |
|---------|-------|-----------------|------|
| 4090 local | Klein 4B (bf16) | ~2s | Free |
| Mac mflux | Klein 4B (q4) | ~7s | Free |
| Mac mflux | Klein 4B (q8) | ~8s | Free |
| Mac mflux | Klein 9B (q8) | ~16s | Free |
| Mac Swift | Dev 32B (int4) | ~12-17min | Free |
| Mac Swift | Dev 32B (qint8) | ~13min | Free |
| BFL API | Klein 4B | ~7s | ~$0.01 |
| BFL API | Dev 32B | ~15s | ~$0.01 |
| BFL API | Pro | ~10s | ~$0.02 |
| BFL API | Max | ~15s | ~$0.03 |

## Pricing

### BFL API (api.bfl.ai) — recommended

| Tier | Endpoint | Cost |
|------|----------|------|
| Max | `flux-2-max` | ~$0.04-0.06/megapixel |
| Pro | `flux-2-pro-preview` | ~$0.03/megapixel |
| Dev | `flux-dev` | ~$0.012/megapixel |
| Fast (Klein) | `flux-2-klein-4b` | ~$0.014/megapixel |
| Kontext Pro | `flux-kontext-pro` | varies |
| Kontext Max | `flux-kontext-max` | varies |

### fal.ai API (fallback)

| Tier | Endpoint | Cost |
|------|----------|------|
| Pro | `fal-ai/flux-2-pro` | ~$0.03/megapixel |
| Fast (Klein) | `fal-ai/flux-2/klein/4b/distilled` | ~$0.009/megapixel |
| Dev | `fal-ai/flux-2/edit` | ~$0.012/megapixel |
| Restyle (Canny) | `fal-ai/flux-control-lora-canny` | ~$0.04/megapixel |

### Local inference

Free (electricity only).
