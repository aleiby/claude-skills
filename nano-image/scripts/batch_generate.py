#!/usr/bin/env python3
"""Generate multiple image options for the same prompt in parallel.

The Gemini API returns exactly 1 image per request, so batch generation
means concurrent API calls. Uses ThreadPoolExecutor for parallelism.

Usage:
    python3 batch_generate.py --prompt "..." --count 4 --model flash
"""

import argparse
import json
import sys
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path
from datetime import datetime

sys.path.insert(0, str(Path(__file__).parent))
from generate_image import generate, VALID_ASPECT_RATIOS, VALID_RESOLUTIONS


def batch_generate(prompt, count=4, model="flash", aspect_ratio="1:1",
                   resolution="1K", output_dir=None, label=None):
    if not output_dir:
        output_dir = Path.cwd() / "nano-image-output"
    else:
        output_dir = Path(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    timestamp = datetime.now().strftime("%Y%m%d-%H%M%S")
    tag = label or "batch"

    results = []
    errors = []

    def gen_one(index):
        output_path = output_dir / f"{tag}-{timestamp}-{index + 1:02d}.png"
        try:
            result = generate(
                prompt=prompt,
                model=model,
                aspect_ratio=aspect_ratio,
                resolution=resolution,
                output_path=str(output_path),
                quiet=True,
            )
            return {"index": index, "result": result}
        except SystemExit:
            return {"index": index, "error": f"Generation {index + 1} failed"}
        except Exception as e:
            return {"index": index, "error": str(e)}

    print(f"Generating {count} options in parallel...", file=sys.stderr)

    # Run concurrently — up to 4 parallel to respect rate limits
    max_workers = min(count, 4)
    with ThreadPoolExecutor(max_workers=max_workers) as pool:
        futures = {pool.submit(gen_one, i): i for i in range(count)}
        for future in as_completed(futures):
            outcome = future.result()
            idx = outcome["index"] + 1
            if "error" in outcome:
                errors.append(outcome)
                print(f"  [{idx}/{count}] failed: {outcome['error']}", file=sys.stderr)
            else:
                results.append(outcome)
                size = outcome["result"].get("file_size_bytes", 0)
                print(f"  [{idx}/{count}] done ({size:,} bytes)", file=sys.stderr)

    # Sort by index for consistent ordering
    results.sort(key=lambda r: r["index"])
    errors.sort(key=lambda r: r["index"])

    # Build batch metadata
    batch_meta = {
        "timestamp": datetime.now().isoformat(),
        "prompt": prompt,
        "model": model,
        "aspect_ratio": aspect_ratio,
        "resolution": resolution,
        "requested": count,
        "succeeded": len(results),
        "failed": len(errors),
        "images": [r["result"] for r in results],
        "errors": [e["error"] for e in errors],
    }
    meta_path = output_dir / f"{tag}-{timestamp}-batch.json"
    meta_path.write_text(json.dumps(batch_meta, indent=2))

    # Summary output (stdout — this is the machine-readable output)
    summary = {
        "status": "success" if results else "failed",
        "requested": count,
        "succeeded": len(results),
        "failed": len(errors),
        "batch_metadata": str(meta_path),
        "images": [r["result"]["output_file"] for r in results],
    }
    if errors:
        summary["errors"] = [e["error"] for e in errors]

    print(json.dumps(summary, indent=2))
    return summary


def main():
    parser = argparse.ArgumentParser(description="Batch generate images with Nano Banana")
    parser.add_argument("--prompt", required=True, help="Image generation prompt")
    parser.add_argument("--count", type=int, default=4, choices=range(2, 9),
                        help="Number of options to generate (2-8, default: 4)")
    parser.add_argument("--model", default="flash", choices=["flash", "pro"],
                        help="Model tier (default: flash)")
    parser.add_argument("--aspect-ratio", default="1:1", choices=VALID_ASPECT_RATIOS,
                        help="Aspect ratio (default: 1:1)")
    parser.add_argument("--resolution", default="1K", choices=VALID_RESOLUTIONS,
                        help="Resolution (default: 1K)")
    parser.add_argument("--output-dir", default=None, help="Output directory")
    parser.add_argument("--label", default=None,
                        help="Label for filenames (default: 'batch')")

    args = parser.parse_args()
    batch_generate(
        prompt=args.prompt,
        count=args.count,
        model=args.model,
        aspect_ratio=args.aspect_ratio,
        resolution=args.resolution,
        output_dir=args.output_dir,
        label=args.label,
    )


if __name__ == "__main__":
    main()
