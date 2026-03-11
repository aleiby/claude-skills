#!/usr/bin/env python3
"""Generate an image using Nano Banana (Gemini image models).

Thin execution tool: takes a prompt and parameters, calls the API,
saves the image and metadata sidecar. No orchestration logic.
"""

import argparse
import base64
import json
import os
import sys
import time
import urllib.request
import urllib.error
from pathlib import Path
from datetime import datetime, timezone


MODELS = {
    "flash": "gemini-3.1-flash-image-preview",
    "pro": "gemini-3-pro-image-preview",
}

VALID_ASPECT_RATIOS = [
    "1:1", "16:9", "9:16", "4:3", "3:4", "3:2", "2:3",
    "4:5", "5:4", "8:1", "1:8", "21:9", "1:4", "4:1",
]

VALID_RESOLUTIONS = ["512", "1K", "2K", "4K"]

API_URL = "https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent"


def get_api_key():
    # Check environment variables in priority order (paid tier first)
    for var in ["GEMINI_API_KEY_PAID_TIER1", "GEMINI_API_KEY"]:
        key = os.environ.get(var)
        if key:
            return key

    # Check common .env locations (paid tier key preferred)
    env_vars_to_find = ["GEMINI_API_KEY_PAID_TIER1", "GEMINI_API_KEY"]
    env_paths = [
        Path.cwd() / ".env",
        Path.home() / ".env",
        Path.home() / ".nano-banana" / ".env",
    ]
    # Also check NANO_IMAGE_ENV_FILE if set (for custom .env locations)
    custom_env = os.environ.get("NANO_IMAGE_ENV_FILE")
    if custom_env:
        env_paths.insert(0, Path(custom_env))
    for env_path in env_paths:
        if env_path.exists():
            # Collect all matching keys from this file
            found = {}
            for line in env_path.read_text().splitlines():
                line = line.strip()
                if not line or line.startswith("#"):
                    continue
                for var in env_vars_to_find:
                    if line.startswith(f"{var}="):
                        val = line.split("=", 1)[1].strip().strip('"').strip("'")
                        if val:
                            found[var] = val
            # Return highest-priority key found in this file
            for var in env_vars_to_find:
                if var in found:
                    return found[var]
    print("ERROR: No Gemini API key found.", file=sys.stderr)
    print("Set GEMINI_API_KEY or GEMINI_API_KEY_PAID_TIER1 via env or .env file.", file=sys.stderr)
    print("Get a key at: https://aistudio.google.com/api-keys", file=sys.stderr)
    sys.exit(1)


def generate(prompt, model="flash", aspect_ratio="1:1", resolution="1K",
             output_path=None, output_dir=None, reference_images=None,
             quiet=False):
    api_key = get_api_key()
    model_id = MODELS.get(model, model)
    url = API_URL.format(model=model_id) + f"?key={api_key}"

    # Build parts
    parts = []

    # Add reference images first if provided
    if reference_images:
        for ref_path in reference_images:
            ref_file = Path(ref_path)
            if not ref_file.exists():
                print(f"WARNING: Reference image not found: {ref_path}", file=sys.stderr)
                continue
            mime = "image/png"
            if ref_file.suffix.lower() in (".jpg", ".jpeg"):
                mime = "image/jpeg"
            elif ref_file.suffix.lower() == ".webp":
                mime = "image/webp"
            img_data = base64.b64encode(ref_file.read_bytes()).decode()
            parts.append({"inline_data": {"mime_type": mime, "data": img_data}})

    # Add text prompt
    parts.append({"text": prompt})

    # Build request body
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

    # Make the request
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

    # Extract image and text from response
    candidates = result.get("candidates", [])
    if not candidates:
        print("ERROR: No candidates in response.", file=sys.stderr)
        print(json.dumps(result, indent=2), file=sys.stderr)
        sys.exit(1)

    image_data = None
    response_text = None

    for part in candidates[0].get("content", {}).get("parts", []):
        # Handle both camelCase (inlineData) and snake_case (inline_data)
        inline = part.get("inline_data") or part.get("inlineData")
        if inline:
            image_data = inline.get("data")
        elif "text" in part:
            response_text = part["text"]

    if not image_data:
        # Sometimes the model returns only text (e.g., safety filter)
        if response_text:
            print(f"Model returned text only (no image): {response_text}", file=sys.stderr)
        else:
            print("ERROR: No image data in response.", file=sys.stderr)
            print(json.dumps(result, indent=2), file=sys.stderr)
        sys.exit(1)

    # Determine output path
    if not output_path:
        if not output_dir:
            output_dir = Path.cwd() / "nano-image-output"
        else:
            output_dir = Path(output_dir)
        output_dir.mkdir(parents=True, exist_ok=True)
        timestamp = datetime.now().strftime("%Y%m%d-%H%M%S")
        output_path = output_dir / f"image-{timestamp}.png"
    else:
        output_path = Path(output_path)
        output_path.parent.mkdir(parents=True, exist_ok=True)

    # Save image
    img_bytes = base64.b64decode(image_data)
    output_path.write_bytes(img_bytes)

    # Save metadata sidecar
    meta = {
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "model": model_id,
        "model_tier": model,
        "prompt": prompt,
        "aspect_ratio": aspect_ratio,
        "resolution": resolution,
        "reference_images": reference_images or [],
        "output_file": str(output_path),
        "file_size_bytes": len(img_bytes),
        "response_text": response_text,
        "usage": result.get("usageMetadata", {}),
    }
    meta_path = output_path.with_suffix(output_path.suffix + ".meta.json")
    meta_path.write_text(json.dumps(meta, indent=2))

    # Output results
    result_info = {
        "status": "success",
        "output_file": str(output_path),
        "metadata_file": str(meta_path),
        "model": model_id,
        "model_tier": model,
        "file_size_bytes": len(img_bytes),
    }
    if response_text:
        result_info["model_description"] = response_text

    if not quiet:
        print(json.dumps(result_info, indent=2))
    return result_info


def main():
    parser = argparse.ArgumentParser(description="Generate an image with Nano Banana")
    parser.add_argument("--prompt", required=True, help="Image generation prompt")
    parser.add_argument("--model", default="flash", choices=["flash", "pro"],
                        help="Model tier (default: flash)")
    parser.add_argument("--aspect-ratio", default="1:1", choices=VALID_ASPECT_RATIOS,
                        help="Aspect ratio (default: 1:1)")
    parser.add_argument("--resolution", default="1K", choices=VALID_RESOLUTIONS,
                        help="Resolution (default: 1K)")
    parser.add_argument("--output", default=None, help="Output file path")
    parser.add_argument("--output-dir", default=None, help="Output directory")
    parser.add_argument("--reference", "-r", action="append", default=None,
                        help="Reference image path (can be repeated)")

    args = parser.parse_args()
    generate(
        prompt=args.prompt,
        model=args.model,
        aspect_ratio=args.aspect_ratio,
        resolution=args.resolution,
        output_path=args.output,
        output_dir=args.output_dir,
        reference_images=args.reference,
    )


if __name__ == "__main__":
    main()
