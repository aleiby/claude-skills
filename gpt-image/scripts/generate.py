#!/usr/bin/env python3
"""Generate or edit images via OpenAI's gpt-image-2 through the Codex CLI.

Wraps `codex exec -s workspace-write [-i ref...] "$imagegen <prompt>"`. Uses
the Codex CLI's existing ChatGPT Pro authentication — no separate API key
needed unless `OPENAI_API_KEY` is set, in which case Codex switches to API
billing automatically.

Generated images go to `./nano-image-output/` by default (shares the gallery
with `flux-art` and `nano-image`). A `.meta.json` sidecar is written
alongside each image with prompt + reference info.
"""

import argparse
import json
import os
import shutil
import subprocess
import sys
import time
from pathlib import Path


CODEX_OUTPUT_DIR = Path.home() / ".codex" / "generated_images"


def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(
        description=__doc__,
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    p.add_argument(
        "--prompt",
        required=True,
        help="The image generation / edit prompt. Pass natural-language scene description.",
    )
    p.add_argument(
        "--input",
        nargs="*",
        default=[],
        help="Optional reference images. Multiple paths allowed (passed as -i to codex).",
    )
    p.add_argument(
        "--output-dir",
        default=None,
        help=(
            "Optional secondary destination — images are ALWAYS placed in "
            "./nano-image-output (so the shared gallery picks them up). If "
            "this is set and differs from nano-image-output, each generated "
            "image is also COPIED to this directory (the gallery copy is the "
            "canonical home; the secondary copy is for project organization)."
        ),
    )
    p.add_argument(
        "--output",
        default=None,
        help="Specific output filename (used only when exactly one image is generated).",
    )
    p.add_argument(
        "--label",
        default="gptimage",
        help="Filename prefix for auto-named outputs.",
    )
    p.add_argument(
        "--timeout",
        type=int,
        default=600,
        help="Seconds before the codex call is killed. Default: 600.",
    )
    return p.parse_args()


IMAGE_SUFFIXES = {".png", ".jpg", ".jpeg", ".webp"}


def snapshot_codex_dir() -> set[Path]:
    """Recursively scan the codex output dir for image files. Codex CLI now
    nests outputs in per-session UUID subdirectories, so the prior flat scan
    (iterdir + is_file) missed every image. Walk the tree and return absolute
    paths so the delta tells us exactly where each new image landed."""
    if not CODEX_OUTPUT_DIR.exists():
        return set()
    return {p for p in CODEX_OUTPUT_DIR.rglob("*") if p.is_file() and p.suffix.lower() in IMAGE_SUFFIXES}


def build_codex_command(prompt: str, refs: list[Path]) -> list[str]:
    cmd = ["codex", "exec", "-s", "workspace-write"]
    for ref in refs:
        cmd += ["-i", str(ref)]
    # `-i` is variadic in codex CLI (`<FILE>...`), so the trailing prompt would
    # be swallowed as another image path without `--` separating them.
    if refs:
        cmd.append("--")
    cmd.append(f"$imagegen {prompt}")
    return cmd


def run_codex(cmd: list[str], timeout: int) -> subprocess.CompletedProcess:
    # codex hangs on stdin if not explicitly closed (known gotcha — see codex skill).
    return subprocess.run(
        cmd,
        stdin=subprocess.DEVNULL,
        capture_output=True,
        text=True,
        timeout=timeout,
    )


GALLERY_DIR_NAME = "nano-image-output"


def main() -> int:
    args = parse_args()

    # Gallery dir is the canonical home so the shared web UI at :8899 always
    # sees new images. --output-dir, when set and different, gets a second copy.
    gallery_dir = (Path.cwd() / GALLERY_DIR_NAME).resolve()
    gallery_dir.mkdir(parents=True, exist_ok=True)
    secondary_dir: Path | None = None
    if args.output_dir:
        secondary_dir = Path(args.output_dir).resolve()
        if secondary_dir == gallery_dir:
            secondary_dir = None
        else:
            secondary_dir.mkdir(parents=True, exist_ok=True)

    refs = [Path(p).resolve() for p in args.input]
    for ref in refs:
        if not ref.exists():
            print(f"[gpt-image] reference not found: {ref}", file=sys.stderr)
            return 1

    before = snapshot_codex_dir()
    cmd = build_codex_command(args.prompt, refs)

    print(
        f"[gpt-image] codex exec ({len(refs)} ref{'s' if len(refs) != 1 else ''}): "
        f"{args.prompt[:80]}{'...' if len(args.prompt) > 80 else ''}",
        file=sys.stderr,
    )

    try:
        result = run_codex(cmd, args.timeout)
    except subprocess.TimeoutExpired:
        print(f"[gpt-image] codex exec timed out after {args.timeout}s", file=sys.stderr)
        return 1
    except FileNotFoundError:
        print("[gpt-image] `codex` not found on PATH — install Codex CLI first.", file=sys.stderr)
        return 1

    if result.returncode != 0:
        print(f"[gpt-image] codex exec failed (exit {result.returncode})", file=sys.stderr)
        if result.stderr:
            print("--- stderr ---", file=sys.stderr)
            print(result.stderr, file=sys.stderr)
        if result.stdout:
            print("--- stdout (last 2000 chars) ---", file=sys.stderr)
            print(result.stdout[-2000:], file=sys.stderr)
        return 1

    if not CODEX_OUTPUT_DIR.exists():
        print(
            f"[gpt-image] codex output dir does not exist ({CODEX_OUTPUT_DIR}); "
            "did codex actually run the imagegen tool?",
            file=sys.stderr,
        )
        print("--- codex stdout ---", file=sys.stderr)
        print(result.stdout, file=sys.stderr)
        return 1

    after = snapshot_codex_dir()
    new_files = sorted(after - before)
    if not new_files:
        print(
            f"[gpt-image] no new images appeared in {CODEX_OUTPUT_DIR} after the codex call.",
            file=sys.stderr,
        )
        print("--- codex stdout ---", file=sys.stderr)
        print(result.stdout, file=sys.stderr)
        return 1

    timestamp = time.strftime("%Y%m%d-%H%M%S")
    new_paths = sorted(new_files, key=lambda p: str(p))
    for i, src in enumerate(new_paths):
        ext = src.suffix or ".png"
        if args.output and len(new_paths) == 1:
            dst_name = args.output
        else:
            suffix = f"-{i}" if len(new_paths) > 1 else ""
            dst_name = f"{args.label}-{timestamp}{suffix}{ext}"

        # Canonical: move into the gallery dir.
        gallery_dst = gallery_dir / dst_name
        shutil.move(str(src), str(gallery_dst))

        meta = {
            "skill": "gpt-image",
            "model": "gpt-image-2",
            "prompt": args.prompt,
            "reference_images": [str(p) for p in refs],
            "timestamp": timestamp,
            "codex_filename": src.name,
            "codex_session_dir": str(src.parent.relative_to(CODEX_OUTPUT_DIR)) if src.parent != CODEX_OUTPUT_DIR else "",
            "output_path": str(gallery_dst),
        }
        meta_path = gallery_dst.with_suffix(gallery_dst.suffix + ".meta.json")
        meta_path.write_text(json.dumps(meta, indent=2))
        print(f"[gpt-image] saved {gallery_dst}")

        # Optional secondary copy for project organization.
        if secondary_dir is not None:
            secondary_dst = secondary_dir / dst_name
            shutil.copy2(str(gallery_dst), str(secondary_dst))
            shutil.copy2(str(meta_path), str(secondary_dst.with_suffix(secondary_dst.suffix + ".meta.json")))
            print(f"[gpt-image] also copied to {secondary_dst}")

    return 0


if __name__ == "__main__":
    sys.exit(main())
