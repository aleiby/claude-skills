# nano-image

A Claude Code skill for image generation and editing using [Nano Banana](https://ai.google.dev/gemini-api/docs/image-generation) (Google Gemini image models).

One orchestrator skill that classifies requests, builds structured specs, chooses the right model tier, generates images, critiques results, and retries automatically.

## Features

- **Generation** — text-to-image with structured prompting
- **Editing** — modify existing images with reference preservation
- **Composition** — combine 2-14 reference images into new outputs
- **Batch generation** — 2-8 parallel variations for exploration
- **Gallery server** — live-updating web gallery at localhost:8899
- **Model escalation** — starts with fast/cheap model, escalates to pro when needed
- **Critique loop** — reviews outputs against a rubric before accepting

## Prerequisites

- Python 3.10+
- A Gemini API key from [aistudio.google.com/api-keys](https://aistudio.google.com/api-keys)

Set the key as an environment variable:

```bash
export GEMINI_API_KEY="your-key-here"
```

Or place it in a `.env` file. The scripts also check for `GEMINI_API_KEY_PAID_TIER1` (preferred if both exist).

## Installation

Clone into your Claude Code skills directory:

```bash
cd ~/.claude/skills
git clone https://github.com/aleiby/claude-skills.git .
# or if this repo is already cloned, the skill is at nano-image/
```

Claude Code discovers the skill automatically from `SKILL.md`.

## Usage

The skill activates automatically when you ask Claude Code for image work:

```
> generate a logo for a coffee shop called Neural Brew
> make a 16:9 hero banner with a mountain landscape
> edit this image to remove the background
> give me 4 variations of this icon concept
> make a flowchart showing the auth flow
```

Or invoke it explicitly:

```
> /nano-image a flat vector illustration of a rocket ship
> /nano-image --pro finalize this as a 4K production asset
```

### Gallery

Start the gallery server to view generated images in your browser:

```bash
python3 ~/.claude/skills/nano-image/scripts/gallery_server.py --port 8899 --dir ./nano-image-output &
```

Then open http://localhost:8899. New images appear automatically as they're generated.

### Batch generation

Generate multiple options in parallel:

```bash
python3 ~/.claude/skills/nano-image/scripts/batch_generate.py \
  --prompt "minimalist mountain logo" \
  --count 4 \
  --model flash \
  --aspect-ratio "1:1" \
  --resolution "1K" \
  --output-dir ./nano-image-output
```

## Model tiers

| Tier | Model | Use for |
|------|-------|---------|
| **flash** | `gemini-3.1-flash-image-preview` | Exploration, drafts, cheap retries |
| **pro** | `gemini-3-pro-image-preview` | Final assets, complex edits, text-heavy images |

The skill starts with flash and escalates to pro after 2 failed retries, or immediately for finalization tasks.

## Structure

```
nano-image/
├── SKILL.md                    # Orchestrator instructions (for Claude)
├── scripts/
│   ├── generate_image.py       # Text-to-image
│   ├── edit_image.py           # Image editing with references
│   ├── compose_images.py       # Multi-image composition
│   ├── batch_generate.py       # Parallel batch generation
│   ├── prompt_to_spec.py       # NL → structured JSON spec
│   └── gallery_server.py       # Live web gallery
├── templates/                  # Spec defaults per task type
│   ├── ui_mockup.json
│   ├── diagram.json
│   └── asset_edit.json
├── rubrics/                    # Review checklists per task type
│   ├── default_review.md
│   ├── ui_review.md
│   └── diagram_review.md
└── presets/                    # Reusable style presets
    ├── clean_modern.json
    ├── warm_editorial.json
    └── technical.json
```

## Design

The skill follows a deliberate separation:

- **SKILL.md** owns orchestration, classification, model selection, and retry logic
- **Scripts** are thin execution tools — no intelligence, no retries, just API calls
- **Templates** provide sensible defaults per task type
- **Rubrics** define explicit pass/fail criteria for the critique step
- **Presets** capture reusable style preferences

This means Claude handles judgment (what to generate, whether to retry, when to escalate) while the scripts stay boring and predictable.
