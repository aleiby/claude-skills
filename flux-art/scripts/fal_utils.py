#!/usr/bin/env python3
"""Shared utilities for flux-art skill: auth, upload, download, metadata."""

import base64
import json
import os
import sys
import urllib.request
import urllib.error
from pathlib import Path
from datetime import datetime, timezone


# --------------------------------------------------------------------------- #
# Local server detection
# --------------------------------------------------------------------------- #

def get_local_url():
    """Return FLUX_LOCAL_URL if set, else check .env files, else None."""
    url = os.environ.get("FLUX_LOCAL_URL")
    if url:
        return url.rstrip("/")

    env_paths = [Path.cwd() / ".env", Path.home() / ".env"]
    for env_path in env_paths:
        if env_path.exists():
            for line in env_path.read_text().splitlines():
                line = line.strip()
                if not line or line.startswith("#"):
                    continue
                if line.startswith("FLUX_LOCAL_URL="):
                    val = line.split("=", 1)[1].strip().strip('"').strip("'")
                    if val:
                        return val.rstrip("/")
    return None


def post_local(base_url, path, body):
    """POST JSON to the local inference server. Returns parsed response."""
    url = f"{base_url}{path}"
    data = json.dumps(body).encode()
    req = urllib.request.Request(
        url,
        data=data,
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    try:
        with urllib.request.urlopen(req, timeout=300) as resp:
            return json.loads(resp.read())
    except urllib.error.HTTPError as e:
        error_body = e.read().decode() if e.fp else ""
        print(f"ERROR: Local server returned {e.code}: {error_body}", file=sys.stderr)
        sys.exit(1)
    except urllib.error.URLError as e:
        print(f"ERROR: Cannot reach local server at {base_url}: {e.reason}",
              file=sys.stderr)
        print("Is serve.py running? Check FLUX_LOCAL_URL.", file=sys.stderr)
        sys.exit(1)


def encode_image_base64(path):
    """Read a local image file and return base64-encoded string."""
    return base64.b64encode(Path(path).read_bytes()).decode()


# --------------------------------------------------------------------------- #
# fal.ai API helpers
# --------------------------------------------------------------------------- #

def get_fal_key():
    """Read FAL_KEY from env or .env files."""
    key = os.environ.get("FAL_KEY")
    if key:
        return key

    env_paths = [
        Path.cwd() / ".env",
        Path.home() / ".env",
    ]

    for env_path in env_paths:
        if env_path.exists():
            for line in env_path.read_text().splitlines():
                line = line.strip()
                if not line or line.startswith("#"):
                    continue
                if line.startswith("FAL_KEY="):
                    val = line.split("=", 1)[1].strip().strip('"').strip("'")
                    if val:
                        return val

    print("ERROR: No fal.ai API key found.", file=sys.stderr)
    print("Set FAL_KEY via env or .env file.", file=sys.stderr)
    print("Get a key at: https://fal.ai/dashboard/keys", file=sys.stderr)
    sys.exit(1)


def ensure_fal_key():
    """Set FAL_KEY in env for fal_client, return key."""
    key = get_fal_key()
    os.environ["FAL_KEY"] = key
    return key


def upload_image(path):
    """Upload a local image to fal CDN, return URL."""
    import fal_client
    return fal_client.upload_file(str(path))


# --------------------------------------------------------------------------- #
# Common helpers
# --------------------------------------------------------------------------- #

def download_image(url, output_path):
    """Download an image from URL to local path. Returns file size in bytes."""
    output_path = Path(output_path)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    req = urllib.request.Request(url)
    with urllib.request.urlopen(req, timeout=120) as resp:
        data = resp.read()
    output_path.write_bytes(data)
    return len(data)


def save_metadata(output_path, meta_dict):
    """Write a .meta.json sidecar file alongside the output image."""
    output_path = Path(output_path)
    meta_path = output_path.with_suffix(output_path.suffix + ".meta.json")
    if "timestamp" not in meta_dict:
        meta_dict["timestamp"] = datetime.now(timezone.utc).isoformat()
    meta_path.write_text(json.dumps(meta_dict, indent=2))
    return str(meta_path)


def make_output_path(output_dir, label=None, index=None, ext="png"):
    """Generate a timestamped output filename."""
    output_dir = Path(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    timestamp = datetime.now().strftime("%Y%m%d-%H%M%S")
    parts = []
    if label:
        parts.append(label)
    parts.append(timestamp)
    if index is not None:
        parts.append(f"{index:02d}")
    filename = "-".join(parts) + f".{ext}"
    return output_dir / filename
