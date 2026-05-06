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
        default="./nano-image-output",
        help="Where to move generated images. Default: ./nano-image-output (shares gallery).",
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


def snapshot_codex_dir() -> set[str]:
    if not CODEX_OUTPUT_DIR.exists():
        return set()
    return {entry.name for entry in CODEX_OUTPUT_DIR.iterdir() if entry.is_file()}


def build_codex_command(prompt: str, refs: list[Path]) -> list[str]:
    cmd = ["codex", "exec", "-s", "workspace-write"]
    for ref in refs:
        cmd += ["-i", str(ref)]
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


def main() -> int:
    args = parse_args()

    output_dir = Path(args.output_dir).resolve()
    output_dir.mkdir(parents=True, exist_ok=True)

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
    moved_paths: list[Path] = []
    for i, name in enumerate(new_files):
        src = CODEX_OUTPUT_DIR / name
        ext = src.suffix or ".png"
        if args.output and len(new_files) == 1:
            dst_name = args.output
        else:
            suffix = f"-{i}" if len(new_files) > 1 else ""
            dst_name = f"{args.label}-{timestamp}{suffix}{ext}"
        dst = output_dir / dst_name
        shutil.move(str(src), str(dst))
        moved_paths.append(dst)

        meta = {
            "skill": "gpt-image",
            "model": "gpt-image-2",
            "prompt": args.prompt,
            "reference_images": [str(p) for p in refs],
            "timestamp": timestamp,
            "codex_filename": name,
            "output_path": str(dst),
        }
        meta_path = dst.with_suffix(dst.suffix + ".meta.json")
        meta_path.write_text(json.dumps(meta, indent=2))
        print(f"[gpt-image] saved {dst}")

    return 0


if __name__ == "__main__":
    sys.exit(main())
