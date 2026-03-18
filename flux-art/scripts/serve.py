#!/usr/bin/env python3
"""FLUX.2 local inference server for the flux-art skill.

Run on a GPU machine (e.g., RTX 4090):

    python3 serve.py --port 8190

Then on the client machine:

    export FLUX_LOCAL_URL=http://<gpu-ip>:8190

Setup (on the GPU machine):

    pip install torch torchvision --index-url https://download.pytorch.org/whl/cu124
    pip install diffusers transformers accelerate sentencepiece protobuf
    pip install fastapi uvicorn pillow

Models are downloaded automatically on first use (~5GB for Klein 4B,
~60GB for Dev). Pre-download with:

    python3 -c "from diffusers import Flux2KleinPipeline; Flux2KleinPipeline.from_pretrained('black-forest-labs/FLUX.2-klein-4B')"
"""

import argparse
import base64
import io
import json
import os
import sys
import threading
import time
from datetime import datetime
from pathlib import Path

# --------------------------------------------------------------------------- #
# Lazy imports — torch/diffusers only needed on the GPU machine
# --------------------------------------------------------------------------- #

def _import_torch():
    import torch
    return torch

def _import_pipeline(tier="fast"):
    """Import the appropriate pipeline class for the given tier.

    Klein 4B uses Flux2KleinPipeline (dedicated, ~13GB VRAM).
    Dev/other tiers fall back to FluxPipeline.
    """
    if tier == "fast":
        try:
            from diffusers import Flux2KleinPipeline
            return Flux2KleinPipeline
        except ImportError:
            print("WARNING: Flux2KleinPipeline not found. "
                  "Upgrade diffusers: pip install git+https://github.com/huggingface/diffusers.git",
                  file=sys.stderr)
    # Fallback for dev tier or if Klein pipeline unavailable
    try:
        from diffusers import FluxPipeline
        return FluxPipeline
    except ImportError:
        pass
    print("ERROR: Could not import FLUX pipeline from diffusers.", file=sys.stderr)
    print("Install: pip install git+https://github.com/huggingface/diffusers.git", file=sys.stderr)
    sys.exit(1)


# --------------------------------------------------------------------------- #
# Model registry
# --------------------------------------------------------------------------- #

MODEL_IDS = {
    "fast": "black-forest-labs/FLUX.2-klein-4B",
    "dev": "black-forest-labs/FLUX.2-dev",
}

# Klein 4B distilled: 4 steps, guidance 1.0
# Dev: 28 steps, guidance 2.5
TIER_DEFAULTS = {
    "fast": {"num_inference_steps": 4, "guidance_scale": 1.0},
    "dev": {"num_inference_steps": 28, "guidance_scale": 2.5},
}

SIZE_PRESETS = {
    "square_hd": (1024, 1024),
    "square": (512, 512),
    "portrait_4_3": (768, 1024),
    "portrait_16_9": (576, 1024),
    "landscape_4_3": (1024, 768),
    "landscape_16_9": (1024, 576),
}

# Aspect ratio aliases (match generate.py client)
SIZE_ALIASES = {
    "16:9": "landscape_16_9",
    "4:3": "landscape_4_3",
    "9:16": "portrait_16_9",
    "3:4": "portrait_4_3",
    "1:1": "square_hd",
}

# Global model cache and lock (one inference at a time on the GPU)
_models = {}
_inference_lock = threading.Lock()


def resolve_size(size_str):
    """Convert size string to (width, height) tuple."""
    if size_str in SIZE_ALIASES:
        size_str = SIZE_ALIASES[size_str]
    if size_str in SIZE_PRESETS:
        return SIZE_PRESETS[size_str]
    if "x" in str(size_str):
        w, h = str(size_str).split("x", 1)
        return (int(w), int(h))
    return SIZE_PRESETS["landscape_4_3"]


def load_model(tier):
    """Load a model tier, caching for reuse."""
    if tier in _models:
        return _models[tier]

    torch = _import_torch()
    PipelineClass = _import_pipeline(tier)
    model_id = MODEL_IDS.get(tier)
    if not model_id:
        raise ValueError(f"Unknown tier: {tier}. Available: {list(MODEL_IDS.keys())}")

    print(f"Loading {tier} model: {model_id} ...", file=sys.stderr)
    print(f"  Pipeline: {PipelineClass.__name__}", file=sys.stderr)
    t0 = time.time()

    pipe = PipelineClass.from_pretrained(
        model_id,
        torch_dtype=torch.bfloat16,
    )

    total_vram = torch.cuda.get_device_properties(0).total_memory / 1024**3
    if tier == "dev" and total_vram <= 32:
        pipe.enable_model_cpu_offload()
        print(f"  CPU offload enabled (dev on {total_vram:.0f}GB card)", file=sys.stderr)
    else:
        pipe.to("cuda")

    dt = time.time() - t0
    print(f"  Loaded in {dt:.1f}s", file=sys.stderr)

    _models[tier] = pipe
    return pipe


def run_inference(pipe, tier, prompt, width, height, seed=None,
                  guidance_scale=None, num_inference_steps=None,
                  num_images=1, input_image=None):
    """Run inference and return list of PIL images + seed used."""
    torch = _import_torch()

    defaults = TIER_DEFAULTS.get(tier, TIER_DEFAULTS["fast"])
    steps = num_inference_steps or defaults["num_inference_steps"]
    guidance = guidance_scale or defaults["guidance_scale"]

    kwargs = {
        "prompt": prompt,
        "width": width,
        "height": height,
        "num_inference_steps": steps,
        "guidance_scale": guidance,
        "num_images_per_prompt": num_images,
    }

    actual_seed = seed if seed is not None else int(time.time()) % (2**32)
    kwargs["generator"] = torch.Generator(device="cuda").manual_seed(actual_seed)

    # Image editing: pass input image if provided
    if input_image is not None:
        kwargs["image"] = input_image

    with _inference_lock:
        result = pipe(**kwargs)

    return result.images, actual_seed


# --------------------------------------------------------------------------- #
# HTTP server (FastAPI)
# --------------------------------------------------------------------------- #

def create_app(output_dir):
    """Create the FastAPI application."""
    from fastapi import FastAPI, HTTPException
    from fastapi.responses import FileResponse, JSONResponse
    from pydantic import BaseModel
    from typing import Optional

    app = FastAPI(title="FLUX.2 Local Server")
    output_dir = Path(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    class GenerateRequest(BaseModel):
        prompt: str
        image_size: str = "landscape_4_3"
        tier: str = "fast"
        seed: Optional[int] = None
        guidance_scale: Optional[float] = None
        num_inference_steps: Optional[int] = None
        num_images: int = 1
        output_format: str = "png"
        input_image_base64: Optional[str] = None

    @app.post("/generate")
    def generate(req: GenerateRequest):
        from PIL import Image

        # Map "pro" to "dev" locally (pro is API-only)
        tier = req.tier
        if tier == "pro":
            tier = "dev"

        # Load model
        try:
            pipe = load_model(tier)
        except Exception as e:
            raise HTTPException(status_code=500, detail=f"Model load failed: {e}")

        # Resolve size
        w, h = resolve_size(req.image_size)

        # Decode input image if provided
        input_image = None
        if req.input_image_base64:
            img_bytes = base64.b64decode(req.input_image_base64)
            input_image = Image.open(io.BytesIO(img_bytes)).convert("RGB")

        # Generate
        t0 = time.time()
        try:
            images, seed_used = run_inference(
                pipe, tier, req.prompt, w, h,
                seed=req.seed,
                guidance_scale=req.guidance_scale,
                num_inference_steps=req.num_inference_steps,
                num_images=req.num_images,
                input_image=input_image,
            )
        except Exception as e:
            raise HTTPException(status_code=500, detail=f"Inference failed: {e}")
        dt = time.time() - t0

        # Save and build response
        result_images = []
        timestamp = datetime.now().strftime("%Y%m%d-%H%M%S")
        for i, img in enumerate(images):
            suffix = f"-{i:02d}" if len(images) > 1 else ""
            filename = f"flux-{timestamp}{suffix}.{req.output_format}"
            filepath = output_dir / filename
            img.save(str(filepath))
            result_images.append({
                "url": f"/images/{filename}",
                "width": img.width,
                "height": img.height,
            })

        return {
            "images": result_images,
            "seed": seed_used,
            "prompt": req.prompt,
            "inference_time": round(dt, 2),
            "tier": tier,
        }

    @app.get("/images/{filename}")
    def get_image(filename: str):
        filepath = output_dir / filename
        if not filepath.exists():
            raise HTTPException(status_code=404)
        return FileResponse(filepath)

    @app.get("/health")
    def health():
        return {
            "status": "ok",
            "models_loaded": list(_models.keys()),
            "available_tiers": list(MODEL_IDS.keys()),
        }

    @app.get("/gpu")
    def gpu_info():
        """Return GPU memory usage and process info."""
        import torch
        import subprocess

        info = {"gpus": [], "processes": []}

        # torch CUDA memory stats
        if torch.cuda.is_available():
            for i in range(torch.cuda.device_count()):
                props = torch.cuda.get_device_properties(i)
                mem = torch.cuda.memory_stats(i) if torch.cuda.memory_allocated(i) > 0 else {}
                info["gpus"].append({
                    "index": i,
                    "name": props.name,
                    "total_mb": round(props.total_memory / 1024**2),
                    "allocated_mb": round(torch.cuda.memory_allocated(i) / 1024**2),
                    "reserved_mb": round(torch.cuda.memory_reserved(i) / 1024**2),
                    "free_mb": round((props.total_memory - torch.cuda.memory_reserved(i)) / 1024**2),
                })

        # nvidia-smi process list
        try:
            result = subprocess.run(
                ["nvidia-smi", "--query-compute-apps=pid,used_gpu_memory,process_name",
                 "--format=csv,noheader,nounits"],
                capture_output=True, text=True, timeout=5,
            )
            for line in result.stdout.strip().split("\n"):
                if line.strip():
                    parts = [p.strip() for p in line.split(",")]
                    if len(parts) >= 3:
                        info["processes"].append({
                            "pid": int(parts[0]),
                            "gpu_memory_mb": int(parts[1]),
                            "name": parts[2],
                        })
        except Exception:
            pass

        return info

    @app.post("/clear-cache")
    def clear_cache():
        """Clear PyTorch CUDA cache to reclaim fragmented memory."""
        import torch
        import gc

        before = torch.cuda.memory_reserved(0) / 1024**2 if torch.cuda.is_available() else 0
        gc.collect()
        torch.cuda.empty_cache()
        after = torch.cuda.memory_reserved(0) / 1024**2 if torch.cuda.is_available() else 0

        return {
            "reserved_before_mb": round(before),
            "reserved_after_mb": round(after),
            "freed_mb": round(before - after),
        }

    @app.post("/unload")
    def unload_model(tier: str = None):
        """Unload model(s) to free GPU/CPU memory.

        POST /unload?tier=fast  — unload just fast
        POST /unload            — unload all models
        """
        import torch
        import gc

        unloaded = []
        if tier:
            if tier in _models:
                del _models[tier]
                unloaded.append(tier)
        else:
            for t in list(_models.keys()):
                del _models[t]
                unloaded.append(t)

        gc.collect()
        if torch.cuda.is_available():
            torch.cuda.empty_cache()

        return {
            "unloaded": unloaded,
            "models_loaded": list(_models.keys()),
        }

    return app


# --------------------------------------------------------------------------- #
# Main
# --------------------------------------------------------------------------- #

def main():
    parser = argparse.ArgumentParser(
        description="FLUX.2 local inference server",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Example:
    # Start server with Klein 4B preloaded
    python3 serve.py --port 8190 --preload fast

    # On the client machine
    export FLUX_LOCAL_URL=http://192.168.1.100:8190
        """,
    )
    parser.add_argument("--host", default="0.0.0.0", help="Bind address (default: 0.0.0.0)")
    parser.add_argument("--port", type=int, default=8190, help="Port (default: 8190)")
    parser.add_argument("--preload", default="fast", choices=["fast", "dev", "none"],
                        help="Preload model on startup (default: fast)")
    parser.add_argument("--output-dir", default="/tmp/flux-art-serve",
                        help="Directory for generated images")

    args = parser.parse_args()

    if args.preload != "none":
        load_model(args.preload)

    import uvicorn
    app = create_app(args.output_dir)
    print(f"\nServer ready at http://{args.host}:{args.port}", file=sys.stderr)
    print(f"  Health: http://{args.host}:{args.port}/health", file=sys.stderr)
    print(f"  Set on client: export FLUX_LOCAL_URL=http://<this-ip>:{args.port}\n",
          file=sys.stderr)
    uvicorn.run(app, host=args.host, port=args.port)


if __name__ == "__main__":
    main()
