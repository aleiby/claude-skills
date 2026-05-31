#!/usr/bin/env python3
"""Compose multiple images using Nano Banana (Gemini image models).

Takes multiple input images and composition instructions.
All input images are sent as references alongside the text prompt.
Saves the result and metadata sidecar. No orchestration logic.
"""

import argparse
import base64
import json
import os
import sys
import urllib.request
import urllib.error
from pathlib import Path
from datetime import datetime, timezone

# Reuse generate_image internals
sys.path.insert(0, str(Path(__file__).parent))
from generate_image import get_api_key, MODELS, API_URL, VALID_ASPECT_RATIOS, VALID_RESOLUTIONS, sniff_image_ext


def compose_images(prompt, input_paths, model="pro", aspect_ratio="16:9",
                   resolution="2K", output_path=None, output_dir=None):
    api_key = get_api_key()
    model_id = MODELS.get(model, model)
    url = API_URL.format(model=model_id) + f"?key={api_key}"

    # Validate all input images exist
    validated_paths = []
    for p in input_paths:
        fp = Path(p)
        if not fp.exists():
            print(f"ERROR: Input image not found: {p}", file=sys.stderr)
            sys.exit(1)
        validated_paths.append(fp)

    if len(validated_paths) < 2:
        print("ERROR: compose_images requires at least 2 input images.", file=sys.stderr)
        sys.exit(1)

    if len(validated_paths) > 14:
        print("WARNING: API supports up to 14 reference images. Using first 14.", file=sys.stderr)
        validated_paths = validated_paths[:14]

    # Build parts: all input images first, then the prompt
    parts = []
    for fp in validated_paths:
        mime = "image/png"
        if fp.suffix.lower() in (".jpg", ".jpeg"):
            mime = "image/jpeg"
        elif fp.suffix.lower() == ".webp":
            mime = "image/webp"
        img_data = base64.b64encode(fp.read_bytes()).decode()
        parts.append({"inline_data": {"mime_type": mime, "data": img_data}})

    parts.append({"text": prompt})

    body = {
        "contents": [{"parts": parts}],
        "generationConfig": {
            "responseModalities": ["TEXT", "IMAGE"],
            "imageConfig": {
                "aspectRatio": aspect_ratio,
                "imageSize": resolution,
            },
        },
    }

    req = urllib.request.Request(
        url,
        data=json.dumps(body).encode(),
        headers={"Content-Type": "application/json"},
        method="POST",
    )

    try:
        with urllib.request.urlopen(req, timeout=180) as resp:
            result = json.loads(resp.read())
    except urllib.error.HTTPError as e:
        error_body = e.read().decode() if e.fp else ""
        print(f"ERROR: API returned {e.code}: {error_body}", file=sys.stderr)
        sys.exit(1)
    except urllib.error.URLError as e:
        print(f"ERROR: Connection failed: {e.reason}", file=sys.stderr)
        sys.exit(1)

    # Extract image and text
    candidates = result.get("candidates", [])
    if not candidates:
        print("ERROR: No candidates in response.", file=sys.stderr)
        print(json.dumps(result, indent=2), file=sys.stderr)
        sys.exit(1)

    output_image_data = None
    output_image_mime = None
    response_text = None

    for part in candidates[0].get("content", {}).get("parts", []):
        inline = part.get("inline_data") or part.get("inlineData")
        if inline:
            output_image_data = inline.get("data")
            output_image_mime = inline.get("mimeType") or inline.get("mime_type")
        elif "text" in part:
            response_text = part["text"]

    if not output_image_data:
        if response_text:
            print(f"Model returned text only (no image): {response_text}", file=sys.stderr)
        else:
            print("ERROR: No image data in response.", file=sys.stderr)
            print(json.dumps(result, indent=2), file=sys.stderr)
        sys.exit(1)

    # Decode first so the file is named by its ACTUAL format (Gemini often
    # returns JPEG; jpeg-in-png files break Godot's importer).
    img_bytes = base64.b64decode(output_image_data)
    true_ext = sniff_image_ext(img_bytes, output_image_mime)

    # Determine output path
    if not output_path:
        if not output_dir:
            output_dir = Path.cwd() / "nano-image-output"
        else:
            output_dir = Path(output_dir)
        output_dir.mkdir(parents=True, exist_ok=True)
        timestamp = datetime.now().strftime("%Y%m%d-%H%M%S")
        output_path = output_dir / f"composed-{timestamp}{true_ext}"
    else:
        output_path = Path(output_path)
        if output_path.suffix.lower() != true_ext:
            output_path = output_path.with_suffix(true_ext)
        output_path.parent.mkdir(parents=True, exist_ok=True)

    # Save image
    output_path.write_bytes(img_bytes)

    # Save metadata sidecar
    meta = {
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "model": model_id,
        "model_tier": model,
        "mode": "compose",
        "prompt": prompt,
        "input_images": [str(p) for p in validated_paths],
        "input_count": len(validated_paths),
        "aspect_ratio": aspect_ratio,
        "resolution": resolution,
        "output_file": str(output_path),
        "file_size_bytes": len(img_bytes),
        "response_text": response_text,
        "usage": result.get("usageMetadata", {}),
    }
    meta_path = output_path.with_suffix(output_path.suffix + ".meta.json")
    meta_path.write_text(json.dumps(meta, indent=2))

    result_info = {
        "status": "success",
        "mode": "compose",
        "output_file": str(output_path),
        "metadata_file": str(meta_path),
        "model": model_id,
        "model_tier": model,
        "input_count": len(validated_paths),
        "file_size_bytes": len(img_bytes),
    }
    if response_text:
        result_info["model_description"] = response_text

    print(json.dumps(result_info, indent=2))
    return result_info


def main():
    parser = argparse.ArgumentParser(description="Compose multiple images with Nano Banana")
    parser.add_argument("--prompt", required=True, help="Composition instructions")
    parser.add_argument("--input", nargs="+", required=True, help="Input image paths (2-14)")
    parser.add_argument("--model", default="pro", choices=["flash", "pro"],
                        help="Model tier (default: pro)")
    parser.add_argument("--aspect-ratio", default="16:9", choices=VALID_ASPECT_RATIOS,
                        help="Aspect ratio (default: 16:9)")
    parser.add_argument("--resolution", default="2K", choices=VALID_RESOLUTIONS,
                        help="Resolution (default: 2K)")
    parser.add_argument("--output", default=None, help="Output file path")
    parser.add_argument("--output-dir", default=None, help="Output directory")

    args = parser.parse_args()
    compose_images(
        prompt=args.prompt,
        input_paths=args.input,
        model=args.model,
        aspect_ratio=args.aspect_ratio,
        resolution=args.resolution,
        output_path=args.output,
        output_dir=args.output_dir,
    )


if __name__ == "__main__":
    main()
