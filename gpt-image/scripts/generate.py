#!/usr/bin/env python3
"""Generate or edit images via OpenAI's gpt-image-2 through the Codex CLI.

Wraps `codex exec --json -s workspace-write [-i ref...] "$imagegen <prompt>"`.
Uses the Codex CLI's existing ChatGPT Pro authentication — no separate API key
needed (billing flows through the ChatGPT plan).

How the image is recovered (changed for codex-cli >= 0.140/0.141):
    The built-in `image_gen` tool NO LONGER writes a PNG to
    `~/.codex/generated_images/` in headless `codex exec` mode. Instead the
    generated image is returned inline as base64 in the `result` field of an
    `image_generation_call` response item, which codex persists ONLY in the
    session rollout JSONL at `~/.codex/sessions/YYYY/MM/DD/rollout-*-<id>.jsonl`.
    So we run codex with `--json` to learn the thread id from stdout, then read
    that thread's rollout file and decode every embedded image.

    A legacy fallback (scan `~/.codex/generated_images/` for files written
    during the call) is kept for older codex versions / interactive saves.

Generated images go to `./nano-image-output/` by default (shares the gallery
with `flux-art` and `nano-image`). A `.meta.json` sidecar is written alongside
each image with prompt + reference info.
"""

import argparse
import base64
import json
import shutil
import sys
import time
from pathlib import Path
import subprocess


CODEX_OUTPUT_DIR = Path.home() / ".codex" / "generated_images"
CODEX_SESSIONS_DIR = Path.home() / ".codex" / "sessions"


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


def detect_ext(raw: bytes) -> str:
    """Map magic bytes to a file extension. gpt-image-2 returns PNG today, but
    don't assume — write whatever format the bytes actually are."""
    if raw[:4] == b"RIFF" and raw[8:12] == b"WEBP":
        return ".webp"
    if raw.startswith(b"\x89PNG\r\n\x1a\n"):
        return ".png"
    if raw.startswith(b"\xff\xd8\xff"):
        return ".jpg"
    if raw[:4] in (b"GIF8",):
        return ".gif"
    return ".png"  # safe default


def build_codex_command(prompt: str, refs: list) -> list:
    # `--json` makes codex print JSONL events to stdout; we read the thread id
    # from the `thread.started` event so we can locate the session rollout.
    cmd = ["codex", "exec", "--json", "-s", "workspace-write"]
    for ref in refs:
        cmd += ["-i", str(ref)]
    # `-i` is variadic in codex CLI (`<FILE>...`), so the trailing prompt would
    # be swallowed as another image path without `--` separating them.
    if refs:
        cmd.append("--")
    # NB: do NOT instruct codex to "save the file" — when asked to write a file
    # the model may fabricate a tiny placeholder PNG with code instead of using
    # the real image_gen output. A plain `$imagegen <prompt>` generates the real
    # image; we recover its bytes from the rollout ourselves.
    cmd.append(f"$imagegen {prompt}")
    return cmd


def run_codex(cmd: list, timeout: int) -> subprocess.CompletedProcess:
    # codex hangs on stdin if not explicitly closed (known gotcha — see codex skill).
    return subprocess.run(
        cmd,
        stdin=subprocess.DEVNULL,
        capture_output=True,
        text=True,
        timeout=timeout,
    )


def extract_thread_id(stdout: str):
    """Pull the codex thread id out of the `--json` event stream on stdout."""
    for line in stdout.splitlines():
        line = line.strip()
        if not line or not line.startswith("{"):
            continue
        try:
            o = json.loads(line)
        except Exception:
            continue
        if o.get("type") == "thread.started" and o.get("thread_id"):
            return o["thread_id"]
        if o.get("thread_id"):
            return o["thread_id"]
    return None


def find_rollout(thread_id: str):
    """Locate the session rollout JSONL for a given thread id."""
    if not CODEX_SESSIONS_DIR.exists():
        return None
    matches = [
        p
        for p in CODEX_SESSIONS_DIR.rglob(f"*{thread_id}*.jsonl")
        if p.is_file()
    ]
    if not matches:
        return None
    return max(matches, key=lambda p: p.stat().st_mtime)


def extract_images_from_rollout(rollout: Path) -> list:
    """Decode every image embedded in `image_generation_call` items.

    Dedupe by the item's id, keeping the latest entry that actually carries a
    `result` blob (an item may appear first with status 'generating' and no
    bytes, then again with the final result)."""
    latest_by_id = {}
    order = []
    with rollout.open() as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            try:
                o = json.loads(line)
            except Exception:
                continue
            if o.get("type") != "response_item":
                continue
            pl = o.get("payload")
            if not isinstance(pl, dict) or pl.get("type") != "image_generation_call":
                continue
            b64 = pl.get("result") or pl.get("b64_json")
            if not isinstance(b64, str) or not b64:
                continue
            iid = pl.get("id") or f"_pos{len(order)}"
            if iid not in latest_by_id:
                order.append(iid)
            latest_by_id[iid] = b64

    out = []
    for iid in order:
        try:
            out.append(base64.b64decode(latest_by_id[iid]))
        except Exception as exc:
            print(f"[gpt-image] failed to decode image {iid}: {exc}", file=sys.stderr)
    return out


def scan_new_disk_images(since: float) -> list:
    """Legacy fallback: bytes of any image file under generated_images written
    during this call (older codex versions / interactive saves still do this)."""
    if not CODEX_OUTPUT_DIR.exists():
        return []
    out = []
    for p in sorted(CODEX_OUTPUT_DIR.rglob("*")):
        if not p.is_file() or p.suffix.lower() not in IMAGE_SUFFIXES:
            continue
        try:
            if p.stat().st_mtime + 0.5 < since:
                continue
            out.append(p.read_bytes())
        except OSError:
            continue
    return out


GALLERY_DIR_NAME = "nano-image-output"


def main() -> int:
    args = parse_args()

    # Gallery dir is the canonical home so the shared web UI at :8899 always
    # sees new images. --output-dir, when set and different, gets a second copy.
    gallery_dir = (Path.cwd() / GALLERY_DIR_NAME).resolve()
    gallery_dir.mkdir(parents=True, exist_ok=True)
    secondary_dir = None
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

    cmd = build_codex_command(args.prompt, refs)
    started = time.time()

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

    # Primary path: recover the image bytes from the session rollout.
    thread_id = extract_thread_id(result.stdout)
    image_blobs = []
    rollout = None
    if thread_id:
        rollout = find_rollout(thread_id)
        if rollout:
            image_blobs = extract_images_from_rollout(rollout)
        else:
            print(
                f"[gpt-image] could not find rollout for thread {thread_id} "
                f"under {CODEX_SESSIONS_DIR}",
                file=sys.stderr,
            )
    else:
        print(
            "[gpt-image] could not parse a thread id from codex --json output.",
            file=sys.stderr,
        )

    # Fallback: legacy on-disk images (older codex / interactive saves).
    if not image_blobs:
        image_blobs = scan_new_disk_images(started)

    if not image_blobs:
        print(
            "[gpt-image] no images recovered from the codex call "
            "(checked the session rollout and ~/.codex/generated_images).",
            file=sys.stderr,
        )
        if rollout:
            print(f"--- rollout inspected: {rollout} ---", file=sys.stderr)
        print("--- codex stdout (last 2000 chars) ---", file=sys.stderr)
        print(result.stdout[-2000:], file=sys.stderr)
        return 1

    timestamp = time.strftime("%Y%m%d-%H%M%S")
    for i, raw in enumerate(image_blobs):
        ext = detect_ext(raw)
        if args.output and len(image_blobs) == 1:
            dst_name = args.output
        else:
            suffix = f"-{i}" if len(image_blobs) > 1 else ""
            dst_name = f"{args.label}-{timestamp}{suffix}{ext}"

        # Canonical: write into the gallery dir.
        gallery_dst = gallery_dir / dst_name
        gallery_dst.write_bytes(raw)

        meta = {
            "skill": "gpt-image",
            "model": "gpt-image-2",
            "prompt": args.prompt,
            "reference_images": [str(p) for p in refs],
            "timestamp": timestamp,
            "codex_thread_id": thread_id,
            "codex_rollout": str(rollout) if rollout else "",
            "bytes": len(raw),
            "output_path": str(gallery_dst),
        }
        meta_path = gallery_dst.with_suffix(gallery_dst.suffix + ".meta.json")
        meta_path.write_text(json.dumps(meta, indent=2))
        print(f"[gpt-image] saved {gallery_dst} ({len(raw)} bytes)")

        # Optional secondary copy for project organization.
        if secondary_dir is not None:
            secondary_dst = secondary_dir / dst_name
            shutil.copy2(str(gallery_dst), str(secondary_dst))
            shutil.copy2(
                str(meta_path),
                str(secondary_dst.with_suffix(secondary_dst.suffix + ".meta.json")),
            )
            print(f"[gpt-image] also copied to {secondary_dst}")

    return 0


if __name__ == "__main__":
    sys.exit(main())
