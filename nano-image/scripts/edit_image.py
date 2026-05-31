#!/usr/bin/env python3
"""Edit an existing image using Nano Banana (Gemini image models).

Takes an input image and editing instructions, sends both to the API.
Saves the result and metadata sidecar. No orchestration logic.
"""

import argparse
import base64
import json
import os
import sys
from pathlib import Path
from datetime import datetime, timezone

# Reuse generate_image internals
sys.path.insert(0, str(Path(__file__).parent))
from generate_image import get_api_key, MODELS, API_URL, VALID_ASPECT_RATIOS, VALID_RESOLUTIONS, sniff_image_ext


def edit_image(prompt, input_path, model="flash", aspect_ratio=None,
               resolution="1K", output_path=None, output_dir=None,
               additional_refs=None):
    api_key = get_api_key()
    model_id = MODELS.get(model, model)
    url = API_URL.format(model=model_id) + f"?key={api_key}"

    input_file = Path(input_path)
    if not input_file.exists():
        print(f"ERROR: Input image not found: {input_path}", file=sys.stderr)
        sys.exit(1)

    # Detect mime type
    mime = "image/png"
    if input_file.suffix.lower() in (".jpg", ".jpeg"):
        mime = "image/jpeg"
    elif input_file.suffix.lower() == ".webp":
        mime = "image/webp"

    # Build parts: input image first, then any additional refs, then prompt
    parts = []

    # Primary input image
    img_data = base64.b64encode(input_file.read_bytes()).decode()
    parts.append({"inline_data": {"mime_type": mime, "data": img_data}})

    # Additional reference images
    if additional_refs:
        for ref_path in additional_refs:
            ref_file = Path(ref_path)
            if not ref_file.exists():
                print(f"WARNING: Reference image not found: {ref_path}", file=sys.stderr)
                continue
            ref_mime = "image/png"
            if ref_file.suffix.lower() in (".jpg", ".jpeg"):
                ref_mime = "image/jpeg"
            elif ref_file.suffix.lower() == ".webp":
                ref_mime = "image/webp"
            ref_data = base64.b64encode(ref_file.read_bytes()).decode()
            parts.append({"inline_data": {"mime_type": ref_mime, "data": ref_data}})

    # Text prompt
    parts.append({"text": prompt})

    # Build image config
    image_config = {"imageSize": resolution}
    if aspect_ratio:
        image_config["aspectRatio"] = aspect_ratio

    body = {
        "contents": [{"parts": parts}],
        "generationConfig": {
            "responseModalities": ["TEXT", "IMAGE"],
            "imageConfig": image_config,
        },
    }

    import urllib.request
    import urllib.error

    req = urllib.request.Request(
        url,
        data=json.dumps(body).encode(),
        headers={"Content-Type": "application/json"},
        method="POST",
    )

    try:
        with urllib.request.urlopen(req, timeout=120) as resp:
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
        # Handle both camelCase (inlineData) and snake_case (inline_data)
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
        stem = input_file.stem
        output_path = output_dir / f"{stem}-edited-{timestamp}{true_ext}"
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
        "mode": "edit",
        "prompt": prompt,
        "input_image": str(input_path),
        "additional_references": additional_refs or [],
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
        "mode": "edit",
        "output_file": str(output_path),
        "metadata_file": str(meta_path),
        "model": model_id,
        "model_tier": model,
        "input_image": str(input_path),
        "file_size_bytes": len(img_bytes),
    }
    if response_text:
        result_info["model_description"] = response_text

    print(json.dumps(result_info, indent=2))
    return result_info


def main():
    parser = argparse.ArgumentParser(description="Edit an image with Nano Banana")
    parser.add_argument("--prompt", required=True, help="Editing instructions")
    parser.add_argument("--input", required=True, help="Input image path")
    parser.add_argument("--model", default="flash", choices=["flash", "pro"],
                        help="Model tier (default: flash)")
    parser.add_argument("--aspect-ratio", default=None, choices=VALID_ASPECT_RATIOS,
                        help="Aspect ratio (default: preserve original)")
    parser.add_argument("--resolution", default="1K", choices=VALID_RESOLUTIONS,
                        help="Resolution (default: 1K)")
    parser.add_argument("--output", default=None, help="Output file path")
    parser.add_argument("--output-dir", default=None, help="Output directory")
    parser.add_argument("--reference", "-r", action="append", default=None,
                        help="Additional reference image (can be repeated)")

    args = parser.parse_args()
    edit_image(
        prompt=args.prompt,
        input_path=args.input,
        model=args.model,
        aspect_ratio=args.aspect_ratio,
        resolution=args.resolution,
        output_path=args.output,
        output_dir=args.output_dir,
        additional_refs=args.reference,
    )


if __name__ == "__main__":
    main()
