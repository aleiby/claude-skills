---
name: nano-image
description: |
  Image generation and editing orchestrator using Nano Banana (Gemini image models).
  Handles generation, editing, composition, diagrams, and iterative refinement.

  INVOKE THIS SKILL when user requests any image work:
  - "generate an image", "make me a picture", "create a visual"
  - "edit this image", "change the background", "remove the text"
  - "make a diagram", "draw a flowchart", "create an infographic"
  - "mock up a UI", "wireframe this", "design a layout"
  - "combine these images", "composite", "moodboard"
  - "make it more polished", "finalize this", "production quality"
user-invocable: true
---

# Nano Image - Orchestrated Image Generation & Editing

## Quick Reference

```
/nano-image <request>        Generate or edit an image
/nano-image --pro <request>  Force pro model
/nano-image --fast <request> Force fast model
/nano-image --gallery        Start the gallery server
/nano-image --help           Show this help
```

## Environment

Requires a Gemini API key. The scripts check in order:
1. `GEMINI_API_KEY_PAID_TIER1` env var (preferred — paid tier)
2. `GEMINI_API_KEY` env var
3. Same vars in `.env` files: `/Users/aleiby/openclaw/.env`, `$CWD/.env`, `~/.env`

Get a key at https://aistudio.google.com/api-keys

## Gallery Server

A live-updating web gallery shows all generated images at **http://localhost:8899**.

Start it (runs in background):
```bash
python3 ~/.claude/skills/nano-image/scripts/gallery_server.py \
  --port 8899 \
  --dir ~/gt/skills/crew/aleiby/nano-image-output &
```

The gallery auto-polls every 3 seconds. New images animate in. Click to lightbox.

## Output Directory

All generated images go to `~/gt/skills/crew/aleiby/nano-image-output/` by default.
Always pass `--output-dir ~/gt/skills/crew/aleiby/nano-image-output` to scripts so
images appear in the gallery. Override with `--output <path>` for specific locations.

## Step 1: Classify the Request

Every image request falls into one of these modes:

| Mode | When | Examples |
|------|------|---------|
| `concept` | New image from scratch | "generate a logo", "make a hero image" |
| `edit` | Modify an existing image | "remove background", "change colors" |
| `compose` | Combine multiple images/refs | "use this style with that layout" |
| `diagram` | Technical/info visual | "draw a flowchart", "architecture diagram" |
| `finalize` | Polish a previous output | "make it production-ready", "4K version" |

Classify the request BEFORE doing anything else.

## Step 2: Choose the Model

### Use FAST model (`gemini-3.1-flash-image-preview`) when:
- User is brainstorming or exploring
- Request is simple / single subject
- No reference images
- Style is loose / "whatever looks good"
- Text fidelity is not critical
- First pass / generating options
- User hasn't specified quality

### Use PRO model (`gemini-3-pro-image-preview`) when:
- User says "final", "polished", "production-ready", "high quality"
- Multiple constraints must be satisfied simultaneously
- Reference images need careful preservation
- Layout/composition is complex
- Text inside the image must be legible and accurate
- Prior fast attempts failed quality checks
- Complex editing with multiple changes
- User explicitly requests `--pro`

### Override rules:
- `--pro` flag always uses pro
- `--fast` flag always uses fast
- `finalize` mode defaults to pro
- Everything else defaults to fast

## Step 3: Build the Structured Spec

Do NOT pass the user's raw request as the prompt. Instead, build a structured spec.

Run the prompt_to_spec script:
```bash
python3 ~/.claude/skills/nano-image/scripts/prompt_to_spec.py --request "user's request here"
```

Or build the spec yourself as JSON with these fields:

```json
{
  "task_type": "concept|edit|compose|diagram|finalize",
  "subject": "main subject description",
  "composition": "how elements are arranged",
  "style": "visual style (photorealistic, illustration, flat, etc.)",
  "palette": "color preferences or constraints",
  "text_content": "any text that must appear in the image",
  "aspect_ratio": "16:9|1:1|9:16|4:3|3:4|etc.",
  "resolution": "1K|2K|4K",
  "background": "background description",
  "constraints": ["must include X", "avoid Y"],
  "negatives": ["things to explicitly avoid"],
  "reference_images": ["paths to reference images"],
  "output_filename": "descriptive-name.png"
}
```

Then convert the spec into a detailed scene description for the prompt. Describe the scene narratively rather than listing keywords.

## Step 4: Generate

Call the generation script:
```bash
# Text-to-image
python3 ~/.claude/skills/nano-image/scripts/generate_image.py \
  --prompt "detailed scene description from spec" \
  --model flash \
  --aspect-ratio "16:9" \
  --resolution "1K" \
  --output-dir ~/gt/skills/crew/aleiby/nano-image-output

# Image editing (with reference)
python3 ~/.claude/skills/nano-image/scripts/edit_image.py \
  --prompt "editing instructions" \
  --input "source-image.png" \
  --model flash \
  --aspect-ratio "16:9" \
  --resolution "1K" \
  --output-dir ~/gt/skills/crew/aleiby/nano-image-output

# Multi-image composition
python3 ~/.claude/skills/nano-image/scripts/compose_images.py \
  --prompt "composition instructions" \
  --input image1.png image2.png image3.png \
  --model pro \
  --aspect-ratio "16:9" \
  --resolution "2K" \
  --output-dir ~/gt/skills/crew/aleiby/nano-image-output
```

The scripts save the image and a `.meta.json` sidecar with full generation details.

## Step 5: Review the Output

After generation, READ the output image file to inspect it visually.

Score against this rubric:

1. **Task adherence**: Does it match what was requested?
2. **Subject accuracy**: Is the main subject correct?
3. **Composition**: Is the layout/arrangement good?
4. **Style match**: Does it match the intended aesthetic?
5. **Text correctness**: If text was requested, is it legible and accurate?
6. **Artifacts**: Any obvious visual problems (extra limbs, distortion, etc.)?

Rate: PASS / RETRY_FAST / RETRY_PRO / FAIL

## Step 6: Retry or Accept

### Retry budget:
- Up to **2 fast retries** with revised spec
- Then **escalate to pro**
- Up to **2 pro retries**
- After that, present best result and ask user

### How to retry:
Do NOT regenerate with the same prompt. Instead:
1. Identify what went wrong from the rubric
2. Patch the spec — tighten specific fields
3. Add the failure to the negatives list
4. Regenerate with the updated spec

### Escalation triggers (fast -> pro):
- Text rendering failed twice
- Complex composition not achieved
- Style fidelity insufficient
- Multiple constraints unsatisfied

## Step 7: Present Result

Tell the user the image is in the gallery (http://localhost:8899). If the gallery
isn't running, mention the output file path.

Also mention:
- Brief description of what was generated
- Model used and resolution
- If you iterated, what was adjusted

Do NOT show the raw JSON spec or technical details unless asked.

## Batch Generation (multiple options)

When the user wants to explore options, generate multiple variations in parallel:
```bash
python3 ~/.claude/skills/nano-image/scripts/batch_generate.py \
  --prompt "detailed scene description" \
  --count 4 \
  --model flash \
  --aspect-ratio "1:1" \
  --resolution "1K" \
  --output-dir ~/gt/skills/crew/aleiby/nano-image-output \
  --label "logo-concepts"
```

- `--count 2-8` — number of parallel options (default: 4)
- `--label` — prefix for filenames (default: "batch")
- Runs up to 4 concurrent API calls
- Writes a `*-batch.json` summary alongside the individual images + sidecars
- All images appear in the gallery automatically

Use batch generation when:
- User says "give me some options", "show me a few variations"
- Exploring visual direction before committing
- Comparing styles or compositions

Do NOT batch when:
- User wants one specific thing
- Editing an existing image
- Finalizing (waste of pro-tier budget)

## Revision Workflow (spec + delta)

When the user asks to revise an existing image:

1. Load the `.meta.json` sidecar from the previous output
2. Build a **delta** — only change the fields that need updating
3. Carry forward the original spec's constraints, negatives, and style
4. For edits to an existing image, use `edit_image.py` with `--input` pointing to the previous output
5. For regeneration with a modified prompt, use `generate_image.py` with the patched spec

This is much better than starting from scratch every time — it preserves intent across iterations.

## Templates

For common request types, use these templates to fill in sensible defaults:

- `~/.claude/skills/nano-image/templates/ui_mockup.json` — UI screenshots, wireframes, app mockups
- `~/.claude/skills/nano-image/templates/diagram.json` — flowcharts, architecture diagrams, infographics
- `~/.claude/skills/nano-image/templates/asset_edit.json` — editing existing images, background removal, style transfer

## Style Presets

Optional style presets can be stored in `~/.claude/skills/nano-image/presets/`.
Each preset is a JSON file with default spec fields (palette, style, constraints,
negatives) that get merged into the spec before generation. Use these for brand
consistency or personal taste preferences.
