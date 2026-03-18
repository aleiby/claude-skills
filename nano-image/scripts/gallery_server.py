#!/usr/bin/env python3
"""Lightweight image gallery server for nano-image output.

Serves a self-updating gallery page that shows generated images
in reverse chronological order with metadata. Auto-polls for new images.

Usage:
    python3 gallery_server.py [--port 8899] [--dir ./nano-image-output]
"""

import argparse
import json
import os
import sys
from http.server import HTTPServer, SimpleHTTPRequestHandler
from pathlib import Path
from urllib.parse import unquote
import mimetypes

DEFAULT_PORT = 8899
DEFAULT_DIR = "./nano-image-output"

GALLERY_HTML = """<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="utf-8">
<title>Nano Image Gallery</title>
<style>
  * { box-sizing: border-box; margin: 0; padding: 0; }
  body {
    font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', system-ui, sans-serif;
    background: #0a0a0a;
    color: #e0e0e0;
    padding: 20px;
  }
  header {
    display: flex;
    justify-content: space-between;
    align-items: center;
    padding: 16px 0;
    border-bottom: 1px solid #222;
    margin-bottom: 24px;
  }
  header h1 { font-size: 20px; font-weight: 500; color: #fff; }
  .status {
    font-size: 13px;
    color: #666;
    display: flex;
    align-items: center;
    gap: 8px;
  }
  .status .dot {
    width: 8px; height: 8px;
    background: #2d2; border-radius: 50%;
    animation: pulse 2s infinite;
  }
  @keyframes pulse {
    0%, 100% { opacity: 1; }
    50% { opacity: 0.4; }
  }
  .grid {
    display: grid;
    grid-template-columns: repeat(auto-fill, minmax(480px, 1fr));
    gap: 24px;
  }
  .card {
    background: #141414;
    border: 1px solid #222;
    border-radius: 12px;
    overflow: hidden;
    transition: border-color 0.2s;
  }
  .card:hover { border-color: #444; }
  .card.new {
    animation: fadeIn 0.5s ease-out;
    border-color: #2d2;
  }
  @keyframes fadeIn {
    from { opacity: 0; transform: translateY(10px); }
    to { opacity: 1; transform: translateY(0); }
  }
  .card img {
    width: 100%;
    display: block;
    cursor: pointer;
    transition: opacity 0.2s;
  }
  .card img:hover { opacity: 0.9; }
  .card .meta {
    padding: 14px 16px;
    font-size: 13px;
    line-height: 1.6;
    color: #999;
  }
  .card .id-label {
    font-family: 'SF Mono', 'Consolas', monospace;
    font-size: 15px;
    font-weight: 600;
    color: #f0c040;
    margin-bottom: 6px;
    letter-spacing: 0.3px;
  }
  .card .meta .prompt {
    color: #ccc;
    font-size: 14px;
    margin-bottom: 8px;
    display: -webkit-box;
    -webkit-line-clamp: 3;
    -webkit-box-orient: vertical;
    overflow: hidden;
  }
  .card .meta .details {
    display: flex;
    gap: 16px;
    flex-wrap: wrap;
  }
  .card .meta .tag {
    background: #1a1a1a;
    padding: 2px 8px;
    border-radius: 4px;
    font-size: 12px;
    color: #888;
  }
  .card .meta .tag.max { color: #f040f0; background: #2a0a2a; }
  .card .meta .tag.pro { color: #f0a020; background: #2a1f0a; }
  .card .meta .tag.dev { color: #40d080; background: #0a2a1a; }
  .card .meta .tag.fast { color: #20c0c0; background: #0a2a2a; }
  .card .meta .tag.flash { color: #20a0f0; background: #0a1a2a; }
  .empty {
    text-align: center;
    padding: 80px 20px;
    color: #444;
  }
  .empty h2 { font-size: 18px; margin-bottom: 8px; color: #666; }
  .lightbox {
    display: none;
    position: fixed;
    top: 0; left: 0; right: 0; bottom: 0;
    background: rgba(0,0,0,0.95);
    z-index: 100;
    cursor: zoom-out;
    justify-content: center;
    align-items: center;
  }
  .lightbox.active { display: flex; }
  .lightbox img {
    max-width: 95vw;
    max-height: 95vh;
    object-fit: contain;
  }
</style>
</head>
<body>
<header>
  <h1>Nano Image Gallery</h1>
  <div class="status">
    <span class="dot"></span>
    <span id="count">0 images</span>
    <span id="lastUpdate"></span>
  </div>
</header>
<div class="grid" id="grid"></div>
<div class="empty" id="empty">
  <h2>No images yet</h2>
  <p>Generate images with the nano-image skill and they'll appear here automatically.</p>
</div>
<div class="lightbox" id="lightbox" onclick="this.classList.remove('active')">
  <img id="lightbox-img" src="">
</div>
<script>
let knownFiles = new Set();
let firstLoad = true;

function openLightbox(src) {
  document.getElementById('lightbox-img').src = src;
  document.getElementById('lightbox').classList.add('active');
}

document.addEventListener('keydown', e => {
  if (e.key === 'Escape') document.getElementById('lightbox').classList.remove('active');
});

function formatTime(ts) {
  try {
    const d = new Date(ts);
    return d.toLocaleTimeString([], {hour: '2-digit', minute: '2-digit'}) +
           ' ' + d.toLocaleDateString([], {month: 'short', day: 'numeric'});
  } catch { return ts; }
}

function formatSize(bytes) {
  if (bytes > 1048576) return (bytes / 1048576).toFixed(1) + ' MB';
  if (bytes > 1024) return (bytes / 1024).toFixed(0) + ' KB';
  return bytes + ' B';
}

async function poll() {
  try {
    const resp = await fetch('/api/images');
    const images = await resp.json();
    const grid = document.getElementById('grid');
    const empty = document.getElementById('empty');
    document.getElementById('count').textContent = images.length + ' image' + (images.length !== 1 ? 's' : '');
    document.getElementById('lastUpdate').textContent = '(updated ' + new Date().toLocaleTimeString() + ')';

    if (images.length === 0) {
      empty.style.display = 'block';
      grid.innerHTML = '';
      firstLoad = false;
      return;
    }
    empty.style.display = 'none';

    // Check for new images
    const newFiles = images.filter(img => !knownFiles.has(img.file));

    if (newFiles.length > 0 || firstLoad) {
      grid.innerHTML = '';
      for (const img of images) {
        const isNew = !firstLoad && !knownFiles.has(img.file);
        const card = document.createElement('div');
        card.className = 'card' + (isNew ? ' new' : '');

        const prompt = img.prompt || 'No prompt recorded';
        const time = img.timestamp ? formatTime(img.timestamp) : '';
        const size = img.file_size_bytes ? formatSize(img.file_size_bytes) : '';
        const res = img.resolution || '';
        const ar = img.aspect_ratio || '';
        const mode = img.mode || 'generate';

        // Model display: prefer specific model name, fall back to tier
        const model = img.model || img.model_tier || 'unknown';
        // Color coding by model family
        let tagClass = 'flash';
        if (model.includes('max')) tagClass = 'max';
        else if (model.includes('pro') || model.includes('kontext')) tagClass = 'pro';
        else if (model.includes('dev')) tagClass = 'dev';
        else if (model.includes('fast') || model.includes('klein')) tagClass = 'fast';
        else if (img.model_tier === 'flux') tagClass = 'pro';

        // Show if it's local
        const isLocal = (img.endpoint || '').startsWith('local:');
        const modelLabel = model + (isLocal ? ' (local)' : '');

        // Build short ID from filename: strip timestamp, keep label + variant
        const shortId = img.file.replace(/\\.png$/i, '')
          .replace(/^(.*?)-\\d{8}-\\d{6}-/, '$1-')
          .replace(/^(.*?)-\\d{8}-\\d{6}$/, '$1');

        card.innerHTML = `
          <img src="/images/${encodeURIComponent(img.file)}" loading="lazy"
               onclick="openLightbox(this.src)" alt="${prompt.substring(0, 80)}">
          <div class="meta">
            <div class="id-label">${shortId}</div>
            <div class="prompt">${prompt.replace(/</g, '&lt;')}</div>
            <div class="details">
              <span class="tag ${tagClass}">${modelLabel}</span>
              ${mode !== 'generate' ? `<span class="tag">${mode}</span>` : ''}
              ${ar ? `<span class="tag">${ar}</span>` : ''}
              ${res ? `<span class="tag">${res}</span>` : ''}
              ${size ? `<span class="tag">${size}</span>` : ''}
              ${time ? `<span class="tag">${time}</span>` : ''}
            </div>
          </div>
        `;
        grid.appendChild(card);
        knownFiles.add(img.file);
      }
      firstLoad = false;
    }
  } catch (err) {
    console.error('Poll error:', err);
  }
}

poll();
setInterval(poll, 3000);
</script>
</body>
</html>"""


class GalleryHandler(SimpleHTTPRequestHandler):
    image_dir = None

    def log_message(self, format, *args):
        # Quieter logging — only errors
        if args and str(args[0]).startswith('4'):
            super().log_message(format, *args)

    def do_GET(self):
        if self.path == '/' or self.path == '/index.html':
            self.send_response(200)
            self.send_header('Content-Type', 'text/html; charset=utf-8')
            self.end_headers()
            self.wfile.write(GALLERY_HTML.encode())

        elif self.path == '/refboard' or self.path == '/refboard/':
            refboard_path = Path(self.image_dir) / 'refboard' / 'index.html'
            if refboard_path.exists():
                self.send_response(200)
                self.send_header('Content-Type', 'text/html; charset=utf-8')
                self.end_headers()
                self.wfile.write(refboard_path.read_bytes())
            else:
                self.send_error(404, 'Reference board not found')

        elif self.path == '/api/images':
            self.send_response(200)
            self.send_header('Content-Type', 'application/json')
            self.send_header('Cache-Control', 'no-cache')
            self.end_headers()
            images = self._list_images()
            self.wfile.write(json.dumps(images).encode())

        elif self.path.startswith('/images/'):
            filename = unquote(self.path[8:])
            filepath = Path(self.image_dir) / filename
            if filepath.exists() and filepath.is_file():
                mime = mimetypes.guess_type(str(filepath))[0] or 'application/octet-stream'
                self.send_response(200)
                self.send_header('Content-Type', mime)
                self.send_header('Cache-Control', 'public, max-age=3600')
                self.send_header('Access-Control-Allow-Origin', '*')
                self.end_headers()
                self.wfile.write(filepath.read_bytes())
            else:
                self.send_error(404)

        else:
            self.send_error(404)

    def _list_images(self):
        """List all images with metadata, newest first."""
        image_dir = Path(self.image_dir)
        if not image_dir.exists():
            return []

        images = []
        for f in sorted(image_dir.iterdir(), key=lambda p: p.stat().st_mtime, reverse=True):
            if f.suffix.lower() in ('.png', '.jpg', '.jpeg', '.webp') and not f.name.endswith('.meta.json'):
                entry = {"file": f.name}

                # Load metadata sidecar if present
                meta_path = f.with_suffix(f.suffix + '.meta.json')
                if meta_path.exists():
                    try:
                        meta = json.loads(meta_path.read_text())
                        entry.update({
                            "prompt": meta.get("prompt", ""),
                            "model": meta.get("model", ""),
                            "model_tier": meta.get("model_tier", ""),
                            "endpoint": meta.get("endpoint", ""),
                            "timestamp": meta.get("timestamp", ""),
                            "aspect_ratio": meta.get("aspect_ratio", ""),
                            "resolution": meta.get("resolution", ""),
                            "file_size_bytes": meta.get("file_size_bytes", 0),
                            "mode": meta.get("mode", "generate"),
                        })
                    except (json.JSONDecodeError, OSError):
                        pass

                if "file_size_bytes" not in entry or not entry.get("file_size_bytes"):
                    entry["file_size_bytes"] = f.stat().st_size

                images.append(entry)

        return images


def main():
    parser = argparse.ArgumentParser(description="Nano Image Gallery Server")
    parser.add_argument("--port", type=int, default=DEFAULT_PORT, help=f"Port (default: {DEFAULT_PORT})")
    parser.add_argument("--dir", default=DEFAULT_DIR, help=f"Image directory (default: {DEFAULT_DIR})")
    args = parser.parse_args()

    image_dir = Path(args.dir).resolve()
    image_dir.mkdir(parents=True, exist_ok=True)

    GalleryHandler.image_dir = str(image_dir)

    server = HTTPServer(("0.0.0.0", args.port), GalleryHandler)
    print(f"Gallery server running at http://localhost:{args.port}")
    print(f"Serving images from: {image_dir}")
    print(f"Press Ctrl+C to stop")

    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\nShutting down.")
        server.shutdown()


if __name__ == "__main__":
    main()
