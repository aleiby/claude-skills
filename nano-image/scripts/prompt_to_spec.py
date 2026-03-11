#!/usr/bin/env python3
"""Convert a natural language image request into a structured JSON spec.

This is a deterministic template-based translator, not an AI call.
It parses the request for known patterns and outputs a spec skeleton
that Claude can review and refine before passing to generate_image.
"""

import argparse
import json
import re
import sys
from pathlib import Path


# Keywords that suggest specific task types
TASK_PATTERNS = {
    "edit": [
        r"\bedit\b", r"\bmodify\b", r"\bchange\b", r"\bremove\b", r"\breplace\b",
        r"\bfix\b", r"\badjust\b", r"\bcrop\b", r"\btrim\b", r"\brotate\b",
        r"\bflip\b", r"\benhance\b", r"\bsharpen\b", r"\bblur\b",
        r"\bbackground\b.*\b(remov|chang|replac)", r"\bcolor correct",
    ],
    "diagram": [
        r"\bdiagram\b", r"\bflowchart\b", r"\bflow chart\b", r"\binfographic\b",
        r"\barchitecture\b", r"\bschematic\b", r"\bwireframe\b", r"\borg chart\b",
        r"\bmind map\b", r"\bprocess flow\b", r"\bdata flow\b", r"\bER diagram\b",
        r"\bsequence diagram\b", r"\bstate diagram\b",
    ],
    "compose": [
        r"\bcombine\b", r"\bcomposite\b", r"\bmerge\b.*\bimages?\b",
        r"\bmoodboard\b", r"\bcollage\b", r"\blayout\b.*\bmultiple\b",
        r"\bside by side\b", r"\bbefore.*after\b",
    ],
    "finalize": [
        r"\bfinalize?\b", r"\bpolish\b", r"\bproduction\b", r"\bfinal\b",
        r"\bhigh.?res\b", r"\b4k\b", r"\bhigh quality\b", r"\bprint.?ready\b",
    ],
}

# Keywords for style detection
STYLE_PATTERNS = {
    "photorealistic": [r"\bphoto\b", r"\brealistic\b", r"\bphotograph\b", r"\bcinematic\b"],
    "illustration": [r"\billustrat\b", r"\bdraw\b", r"\bsketch\b", r"\bcartoon\b", r"\banime\b"],
    "flat": [r"\bflat\b", r"\bminimal\b", r"\bclean\b", r"\bsimple\b", r"\bicon\b"],
    "editorial": [r"\beditorial\b", r"\bmagazine\b", r"\bartistic\b"],
    "3d": [r"\b3d\b", r"\brender\b", r"\bisometric\b", r"\bblender\b"],
    "pixel-art": [r"\bpixel\b", r"\bretro\b", r"\b8.?bit\b", r"\b16.?bit\b"],
    "watercolor": [r"\bwatercolor\b", r"\bwatercolour\b", r"\bpainting\b"],
}

# Aspect ratio detection
ASPECT_PATTERNS = {
    "16:9": [r"\b16[:/x]9\b", r"\bwidescreen\b", r"\blandscape\b", r"\bbanner\b", r"\bhero\b"],
    "9:16": [r"\b9[:/x]16\b", r"\bportrait\b", r"\bstory\b", r"\bmobile\b", r"\bphone\b"],
    "1:1": [r"\b1[:/x]1\b", r"\bsquare\b", r"\bprofile\b", r"\bavatar\b", r"\bicon\b", r"\bthumbnail\b"],
    "4:3": [r"\b4[:/x]3\b", r"\bslide\b", r"\bpresentation\b"],
    "3:4": [r"\b3[:/x]4\b"],
    "4:5": [r"\b4[:/x]5\b", r"\binstagram\b"],
    "21:9": [r"\b21[:/x]9\b", r"\bultrawide\b"],
}

# Resolution detection
RESOLUTION_PATTERNS = {
    "512": [r"\b512\b", r"\btiny\b", r"\bthumb\b"],
    "1K": [r"\b1k\b", r"\b1024\b"],
    "2K": [r"\b2k\b", r"\b2048\b"],
    "4K": [r"\b4k\b", r"\b4096\b", r"\bhigh.?res\b", r"\bprint\b"],
}


def detect_pattern(text, patterns):
    """Return the first matching category from a pattern dict."""
    text_lower = text.lower()
    for category, regexes in patterns.items():
        for pattern in regexes:
            if re.search(pattern, text_lower):
                return category
    return None


def build_spec(request, template=None):
    """Build a structured spec from a natural language request."""
    # Detect task type
    task_type = detect_pattern(request, TASK_PATTERNS) or "concept"

    # Detect style
    style = detect_pattern(request, STYLE_PATTERNS)

    # Detect aspect ratio
    aspect_ratio = detect_pattern(request, ASPECT_PATTERNS) or "1:1"

    # Detect resolution
    resolution = detect_pattern(request, RESOLUTION_PATTERNS) or "1K"

    # Load template defaults if specified
    defaults = {}
    if template:
        template_path = Path(__file__).parent.parent / "templates" / f"{template}.json"
        if template_path.exists():
            defaults = json.loads(template_path.read_text())

    spec = {
        "task_type": task_type,
        "subject": request,  # Claude should refine this
        "composition": defaults.get("composition", ""),
        "style": style or defaults.get("style", ""),
        "palette": defaults.get("palette", ""),
        "text_content": "",
        "aspect_ratio": aspect_ratio,
        "resolution": resolution,
        "background": defaults.get("background", ""),
        "constraints": defaults.get("constraints", []),
        "negatives": defaults.get("negatives", []),
        "reference_images": [],
        "output_filename": "",
    }

    # Apply template-specific overrides
    if task_type == "diagram":
        spec.setdefault("style", "flat")
        if not spec["negatives"]:
            spec["negatives"] = ["photorealistic textures", "gradients", "shadows"]

    return spec


def main():
    parser = argparse.ArgumentParser(
        description="Convert a natural language request into a structured image spec"
    )
    parser.add_argument("--request", required=True, help="Natural language image request")
    parser.add_argument("--template", default=None,
                        choices=["ui_mockup", "diagram", "asset_edit"],
                        help="Template to apply defaults from")
    parser.add_argument("--pretty", action="store_true", default=True,
                        help="Pretty-print JSON output")

    args = parser.parse_args()
    spec = build_spec(args.request, args.template)
    print(json.dumps(spec, indent=2 if args.pretty else None))


if __name__ == "__main__":
    main()
