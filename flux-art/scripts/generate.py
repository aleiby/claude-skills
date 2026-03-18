#!/usr/bin/env python3
"""Generate images using FLUX.2 via BFL API, fal.ai, or a local inference server.

Handles text-to-image (no --input) and image editing (with --input).
Supports Max (best), Pro (production), Fast/Klein (speed), and Dev (full control) tiers.

Routing:
  --tier max/pro  → BFL API (api.bfl.ai) if BFL_API_KEY set, else fal.ai
  --tier fast/dev → FLUX_LOCAL_URL if set, else BFL API, else fal.ai
"""

import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
from fal_utils import (
    get_local_url, post_local, encode_image_base64,
    ensure_fal_key, upload_image, download_image, save_metadata, make_output_path,
    get_bfl_key, post_bfl, BFL_ENDPOINTS,
)

ENDPOINTS = {
    "pro": "fal-ai/flux-2-pro",
    "pro-edit": "fal-ai/flux-2-pro/edit",
    "fast": "fal-ai/flux-2/klein/4b/distilled",
    "dev": "fal-ai/flux-2/edit",
}

IMAGE_SIZE_ALIASES = {
    "16:9": "landscape_16_9",
    "4:3": "landscape_4_3",
    "9:16": "portrait_16_9",
    "3:4": "portrait_4_3",
    "1:1": "square_hd",
}

VALID_IMAGE_SIZES = [
    "square_hd", "square", "portrait_4_3", "portrait_16_9",
    "landscape_4_3", "landscape_16_9",
]


def resolve_image_size(size_str):
    """Convert aspect ratio string or preset name to API-compatible value."""
    if not size_str:
        return "landscape_4_3"
    if size_str in IMAGE_SIZE_ALIASES:
        return IMAGE_SIZE_ALIASES[size_str]
    if size_str in VALID_IMAGE_SIZES:
        return size_str
    if "x" in size_str:
        w, h = size_str.split("x", 1)
        return {"width": int(w), "height": int(h)}
    return size_str


# --------------------------------------------------------------------------- #
# Local server path
# --------------------------------------------------------------------------- #

def generate_local(local_url, prompt, input_image=None, image_size="landscape_4_3",
                   tier="fast", guidance_scale=None, num_inference_steps=None,
                   seed=None, num_images=1, output_format="png",
                   output_path=None, output_dir=None, label=None):
    """Generate via local FLUX.2 inference server."""
    resolved_size = resolve_image_size(image_size)

    body = {
        "prompt": prompt,
        "image_size": str(resolved_size) if isinstance(resolved_size, str) else f"{resolved_size['width']}x{resolved_size['height']}",
        "tier": tier,
        "num_images": num_images,
        "output_format": output_format,
    }

    if seed is not None:
        body["seed"] = seed
    if guidance_scale is not None:
        body["guidance_scale"] = guidance_scale
    if num_inference_steps is not None:
        body["num_inference_steps"] = num_inference_steps
    if input_image:
        body["input_image_base64"] = encode_image_base64(input_image)
        print(f"Encoded input image: {input_image}", file=sys.stderr)

    actual_tier = "dev" if tier == "pro" else tier
    print(f"Calling local server ({actual_tier} tier)...", file=sys.stderr)
    result = post_local(local_url, "/generate", body)

    images = result.get("images", [])
    if not images:
        print("ERROR: No images in response.", file=sys.stderr)
        print(json.dumps(result, indent=2), file=sys.stderr)
        sys.exit(1)

    if not output_dir:
        output_dir = Path.cwd() / "nano-image-output"

    outputs = []
    for i, img in enumerate(images):
        if output_path and len(images) == 1:
            out_path = Path(output_path)
            out_path.parent.mkdir(parents=True, exist_ok=True)
        else:
            idx = i if len(images) > 1 else None
            out_path = make_output_path(
                output_dir, label=label or "flux", index=idx, ext=output_format,
            )

        # Download from local server (relative URL → full URL)
        img_url = img["url"]
        if img_url.startswith("/"):
            img_url = f"{local_url}{img_url}"
        file_size = download_image(img_url, out_path)

        meta = {
            "model": f"flux-2-{actual_tier}-local",
            "model_tier": "flux",
            "endpoint": f"local:{actual_tier}",
            "prompt": prompt,
            "image_size": str(resolved_size),
            "seed": result.get("seed"),
            "output_format": output_format,
            "input_image": str(input_image) if input_image else None,
            "output_file": str(out_path),
            "file_size_bytes": file_size,
            "image_width": img.get("width"),
            "image_height": img.get("height"),
            "inference_time": result.get("inference_time"),
        }
        meta_path = save_metadata(out_path, meta)

        outputs.append({
            "output_file": str(out_path),
            "metadata_file": meta_path,
            "width": img.get("width"),
            "height": img.get("height"),
            "file_size_bytes": file_size,
        })

    result_info = {
        "status": "success",
        "model": f"flux-2-{actual_tier}-local",
        "model_tier": "flux",
        "endpoint": f"local:{actual_tier}",
        "images": outputs,
        "inference_time": result.get("inference_time"),
    }
    print(json.dumps(result_info, indent=2))
    return result_info


# --------------------------------------------------------------------------- #
# BFL API path (api.bfl.ai — Black Forest Labs direct)
# --------------------------------------------------------------------------- #

def generate_bfl(prompt, input_image=None, image_size="landscape_4_3",
                 tier="pro", seed=None, output_format="png",
                 output_path=None, output_dir=None, label=None):
    """Generate via BFL API (api.bfl.ai)."""
    resolved_size = resolve_image_size(image_size)

    # BFL uses width/height directly, not preset names
    if isinstance(resolved_size, dict):
        width, height = resolved_size["width"], resolved_size["height"]
    else:
        size_map = {
            "square_hd": (1024, 1024), "square": (512, 512),
            "portrait_4_3": (768, 1024), "portrait_16_9": (576, 1024),
            "landscape_4_3": (1024, 768), "landscape_16_9": (1024, 576),
        }
        width, height = size_map.get(resolved_size, (1024, 768))

    # Map tier to BFL endpoint
    bfl_tier = tier
    if tier == "fast":
        bfl_tier = "klein"
    endpoint = BFL_ENDPOINTS.get(bfl_tier, BFL_ENDPOINTS["pro"])

    body = {
        "prompt": prompt,
        "width": width,
        "height": height,
    }
    if seed is not None:
        body["seed"] = seed
    if output_format:
        body["output_format"] = output_format

    print(f"Calling BFL API ({endpoint})...", file=sys.stderr)
    result = post_bfl(endpoint, body)

    # BFL returns result.url (single image) or result.images
    image_url = result.get("result", {}).get("sample") if isinstance(result.get("result"), dict) else None
    if not image_url:
        # Try alternative response shapes
        image_url = result.get("sample") or result.get("url")
    if not image_url:
        print(f"ERROR: Unexpected BFL response: {json.dumps(result, indent=2)}", file=sys.stderr)
        sys.exit(1)

    if not output_dir:
        output_dir = Path.cwd() / "nano-image-output"

    if output_path:
        out_path = Path(output_path)
        out_path.parent.mkdir(parents=True, exist_ok=True)
    else:
        out_path = make_output_path(
            output_dir, label=label or "flux", ext=output_format,
        )

    file_size = download_image(image_url, out_path)

    meta = {
        "model": f"flux-2-{tier}",
        "model_tier": "flux",
        "endpoint": f"bfl:{endpoint}",
        "prompt": prompt,
        "image_size": f"{width}x{height}",
        "seed": result.get("seed"),
        "output_format": output_format,
        "output_file": str(out_path),
        "file_size_bytes": file_size,
        "image_width": width,
        "image_height": height,
    }
    meta_path = save_metadata(out_path, meta)

    result_info = {
        "status": "success",
        "model": f"flux-2-{tier}",
        "model_tier": "flux",
        "endpoint": f"bfl:{endpoint}",
        "images": [{
            "output_file": str(out_path),
            "metadata_file": meta_path,
            "width": width,
            "height": height,
            "file_size_bytes": file_size,
        }],
    }
    print(json.dumps(result_info, indent=2))
    return result_info


# --------------------------------------------------------------------------- #
# fal.ai API path
# --------------------------------------------------------------------------- #

def generate_fal(prompt, input_image=None, image_size="landscape_4_3",
                 tier="pro", guidance_scale=None, num_inference_steps=None,
                 seed=None, num_images=1, output_format="png",
                 output_path=None, output_dir=None, label=None):
    """Generate via fal.ai API."""
    ensure_fal_key()
    import fal_client

    resolved_size = resolve_image_size(image_size)

    # Choose endpoint based on tier and whether input image is provided
    if input_image:
        if tier == "fast":
            tier = "dev"
            print("Note: Klein doesn't support editing, using dev tier", file=sys.stderr)
        if tier == "pro":
            endpoint = ENDPOINTS["pro-edit"]
        else:
            endpoint = ENDPOINTS["dev"]
        image_urls = [upload_image(input_image)]
        print(f"Uploaded input image: {image_urls[0]}", file=sys.stderr)
    else:
        endpoint = ENDPOINTS.get(tier, ENDPOINTS["pro"])
        image_urls = None

    args = {
        "prompt": prompt,
        "output_format": output_format,
        "image_size": resolved_size,
    }

    if image_urls:
        args["image_urls"] = image_urls

    if seed is not None:
        args["seed"] = seed

    if tier == "dev":
        if guidance_scale is not None:
            args["guidance_scale"] = guidance_scale
        if num_inference_steps is not None:
            args["num_inference_steps"] = num_inference_steps
        if num_images > 1:
            args["num_images"] = num_images

    print(f"Calling {endpoint} ({tier} tier)...", file=sys.stderr)
    result = fal_client.subscribe(endpoint, arguments=args)

    images = result.get("images", [])
    if not images:
        print("ERROR: No images in response.", file=sys.stderr)
        print(json.dumps(result, indent=2), file=sys.stderr)
        sys.exit(1)

    if not output_dir:
        output_dir = Path.cwd() / "nano-image-output"

    outputs = []
    for i, img in enumerate(images):
        if output_path and len(images) == 1:
            out_path = Path(output_path)
            out_path.parent.mkdir(parents=True, exist_ok=True)
        else:
            idx = i if len(images) > 1 else None
            out_path = make_output_path(
                output_dir, label=label or "flux", index=idx, ext=output_format,
            )

        file_size = download_image(img["url"], out_path)

        meta = {
            "model": f"flux-2-{tier}",
            "model_tier": "flux",
            "endpoint": endpoint,
            "prompt": prompt,
            "image_size": str(resolved_size),
            "seed": result.get("seed"),
            "output_format": output_format,
            "input_image": str(input_image) if input_image else None,
            "output_file": str(out_path),
            "file_size_bytes": file_size,
            "image_width": img.get("width"),
            "image_height": img.get("height"),
        }
        if guidance_scale is not None and tier == "dev":
            meta["guidance_scale"] = guidance_scale
        meta_path = save_metadata(out_path, meta)

        outputs.append({
            "output_file": str(out_path),
            "metadata_file": meta_path,
            "width": img.get("width"),
            "height": img.get("height"),
            "file_size_bytes": file_size,
        })

    result_info = {
        "status": "success",
        "model": f"flux-2-{tier}",
        "model_tier": "flux",
        "endpoint": endpoint,
        "images": outputs,
    }
    print(json.dumps(result_info, indent=2))
    return result_info


# --------------------------------------------------------------------------- #
# Entry point
# --------------------------------------------------------------------------- #

def generate(prompt, input_image=None, image_size="landscape_4_3",
             tier="pro", guidance_scale=None, num_inference_steps=None,
             seed=None, num_images=1, output_format="png",
             output_path=None, output_dir=None, label=None, backend=None):
    """Route to local server, BFL API, or fal.ai.

    backend=None (auto):
      1. Local server (FLUX_LOCAL_URL) for fast/dev tiers
      2. BFL API (BFL_API_KEY) for all tiers (max only available here)
      3. fal.ai (FAL_KEY) as fallback
    backend="local"/"bfl"/"fal": force specific backend.
    """
    local_url = get_local_url()
    bfl_key = get_bfl_key()

    if backend == "local":
        if not local_url:
            print("ERROR: --backend local but FLUX_LOCAL_URL not set.", file=sys.stderr)
            sys.exit(1)
        return generate_local(
            local_url, prompt, input_image=input_image, image_size=image_size,
            tier=tier, guidance_scale=guidance_scale,
            num_inference_steps=num_inference_steps, seed=seed,
            num_images=num_images, output_format=output_format,
            output_path=output_path, output_dir=output_dir, label=label,
        )

    if backend == "bfl":
        return generate_bfl(
            prompt, input_image=input_image, image_size=image_size,
            tier=tier, seed=seed, output_format=output_format,
            output_path=output_path, output_dir=output_dir, label=label,
        )

    if backend == "fal":
        return generate_fal(
            prompt, input_image=input_image, image_size=image_size,
            tier=tier, guidance_scale=guidance_scale,
            num_inference_steps=num_inference_steps, seed=seed,
            num_images=num_images, output_format=output_format,
            output_path=output_path, output_dir=output_dir, label=label,
        )

    # Auto routing
    # Local server handles fast/dev tiers
    if local_url and tier in ("fast", "dev"):
        return generate_local(
            local_url, prompt, input_image=input_image, image_size=image_size,
            tier=tier, guidance_scale=guidance_scale,
            num_inference_steps=num_inference_steps, seed=seed,
            num_images=num_images, output_format=output_format,
            output_path=output_path, output_dir=output_dir, label=label,
        )

    # BFL API for pro/max or when no local server
    if bfl_key:
        return generate_bfl(
            prompt, input_image=input_image, image_size=image_size,
            tier=tier, seed=seed, output_format=output_format,
            output_path=output_path, output_dir=output_dir, label=label,
        )

    # fal.ai fallback
    return generate_fal(
        prompt, input_image=input_image, image_size=image_size,
        tier=tier, guidance_scale=guidance_scale,
        num_inference_steps=num_inference_steps, seed=seed,
        num_images=num_images, output_format=output_format,
        output_path=output_path, output_dir=output_dir, label=label,
    )


def main():
    parser = argparse.ArgumentParser(description="Generate images with FLUX.2")
    parser.add_argument("--prompt", required=True, help="Image generation prompt")
    parser.add_argument("--input", default=None,
                        help="Input image path (enables editing mode)")
    parser.add_argument("--image-size", default="landscape_4_3",
                        help="Size: preset name, aspect ratio (16:9), or WxH (1920x1080)")
    parser.add_argument("--tier", default="pro", choices=["max", "pro", "fast", "dev"],
                        help="Model tier: max (best), pro (production), fast (klein), dev (full control)")
    parser.add_argument("--guidance-scale", type=float, default=None,
                        help="CFG guidance scale (dev tier only)")
    parser.add_argument("--num-inference-steps", type=int, default=None,
                        help="Inference steps (dev tier only)")
    parser.add_argument("--seed", type=int, default=None, help="Random seed")
    parser.add_argument("--num-images", type=int, default=1,
                        help="Number of images (dev tier only, default: 1)")
    parser.add_argument("--output-format", default="png", choices=["png", "jpeg"],
                        help="Output format (default: png)")
    parser.add_argument("--output", default=None, help="Specific output file path")
    parser.add_argument("--output-dir", default=None, help="Output directory")
    parser.add_argument("--label", default=None, help="Filename prefix label")
    parser.add_argument("--backend", default=None, choices=["local", "bfl", "fal"],
                        help="Force backend: local (4090), bfl (api.bfl.ai), fal (fal.ai)")

    args = parser.parse_args()
    generate(
        prompt=args.prompt,
        input_image=args.input,
        image_size=args.image_size,
        tier=args.tier,
        guidance_scale=args.guidance_scale,
        num_inference_steps=args.num_inference_steps,
        seed=args.seed,
        num_images=args.num_images,
        output_format=args.output_format,
        output_path=args.output,
        output_dir=args.output_dir,
        label=args.label,
        backend=args.backend,
    )


if __name__ == "__main__":
    main()
