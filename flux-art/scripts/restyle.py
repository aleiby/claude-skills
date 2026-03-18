#!/usr/bin/env python3
"""Restyle a screenshot as concept art using FLUX Control LoRA Canny via fal.ai.

Preserves the structural composition of the input image (via canny edge detection)
while applying a new artistic style driven by the text prompt.
"""

import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
from fal_utils import (
    ensure_fal_key, upload_image, download_image, save_metadata, make_output_path,
)

ENDPOINT = "fal-ai/flux-control-lora-canny/image-to-image"

VALID_IMAGE_SIZES = [
    "square_hd", "square", "portrait_4_3", "portrait_16_9",
    "landscape_4_3", "landscape_16_9",
]


def restyle(prompt, input_image, image_size="landscape_16_9", guidance_scale=3.5,
            num_inference_steps=28, strength=0.85, control_strength=1.0,
            seed=None, num_images=1, output_format="png", output_path=None,
            output_dir=None, label=None):
    ensure_fal_key()
    import fal_client

    # Upload the screenshot — used as both base image and canny control source
    image_url = upload_image(input_image)
    print(f"Uploaded input image: {image_url}", file=sys.stderr)

    # Build API arguments
    args = {
        "prompt": prompt,
        "image_url": image_url,
        "control_lora_image_url": image_url,
        "guidance_scale": guidance_scale,
        "num_inference_steps": num_inference_steps,
        "strength": strength,
        "control_lora_strength": control_strength,
        "num_images": num_images,
        "output_format": output_format,
    }

    # Parse image_size — either a preset name or WxH custom size
    if "x" in str(image_size):
        w, h = image_size.split("x", 1)
        args["image_size"] = {"width": int(w), "height": int(h)}
    else:
        args["image_size"] = image_size

    if seed is not None:
        args["seed"] = seed

    print(f"Calling {ENDPOINT}...", file=sys.stderr)
    result = fal_client.subscribe(ENDPOINT, arguments=args)

    # Process results
    images = result.get("images", [])
    if not images:
        print("ERROR: No images in response.", file=sys.stderr)
        print(json.dumps(result, indent=2), file=sys.stderr)
        sys.exit(1)

    if not output_dir:
        output_dir = Path.cwd() / "nano-image-output"

    outputs = []
    for i, img in enumerate(images):
        if output_path and num_images == 1:
            out_path = Path(output_path)
            out_path.parent.mkdir(parents=True, exist_ok=True)
        else:
            idx = i if num_images > 1 else None
            out_path = make_output_path(
                output_dir, label=label or "restyle", index=idx, ext=output_format,
            )

        file_size = download_image(img["url"], out_path)

        meta = {
            "model": "flux-control-lora-canny",
            "model_tier": "flux",
            "endpoint": ENDPOINT,
            "prompt": prompt,
            "input_image": str(input_image),
            "image_size": image_size,
            "guidance_scale": guidance_scale,
            "num_inference_steps": num_inference_steps,
            "strength": strength,
            "control_lora_strength": control_strength,
            "seed": result.get("seed"),
            "output_format": output_format,
            "output_file": str(out_path),
            "file_size_bytes": file_size,
            "image_width": img.get("width"),
            "image_height": img.get("height"),
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
        "model": "flux-control-lora-canny",
        "model_tier": "flux",
        "endpoint": ENDPOINT,
        "images": outputs,
    }
    print(json.dumps(result_info, indent=2))
    return result_info


def main():
    parser = argparse.ArgumentParser(
        description="Restyle a screenshot as concept art (structure-preserving)")
    parser.add_argument("--prompt", required=True,
                        help="Target art style description")
    parser.add_argument("--input", required=True,
                        help="Input screenshot path (required)")
    parser.add_argument("--image-size", default="landscape_16_9",
                        help="Output size: preset name or WxH (default: landscape_16_9)")
    parser.add_argument("--guidance-scale", type=float, default=3.5,
                        help="CFG guidance scale (default: 3.5)")
    parser.add_argument("--num-inference-steps", type=int, default=28,
                        help="Inference steps (default: 28)")
    parser.add_argument("--strength", type=float, default=0.85,
                        help="Transform strength 0.01-1.0 (default: 0.85)")
    parser.add_argument("--control-strength", type=float, default=1.0,
                        help="Canny edge control strength 0-2 (default: 1.0)")
    parser.add_argument("--seed", type=int, default=None, help="Random seed")
    parser.add_argument("--num-images", type=int, default=1,
                        help="Number of images 1-4 (default: 1)")
    parser.add_argument("--output-format", default="png", choices=["png", "jpeg"],
                        help="Output format (default: png)")
    parser.add_argument("--output", default=None, help="Specific output file path")
    parser.add_argument("--output-dir", default=None, help="Output directory")
    parser.add_argument("--label", default=None, help="Filename prefix label")

    args = parser.parse_args()
    restyle(
        prompt=args.prompt,
        input_image=args.input,
        image_size=args.image_size,
        guidance_scale=args.guidance_scale,
        num_inference_steps=args.num_inference_steps,
        strength=args.strength,
        control_strength=args.control_strength,
        seed=args.seed,
        num_images=min(max(args.num_images, 1), 4),
        output_format=args.output_format,
        output_path=args.output,
        output_dir=args.output_dir,
        label=args.label,
    )


if __name__ == "__main__":
    main()
