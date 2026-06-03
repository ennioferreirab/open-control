#!/usr/bin/env python3
# /// script
# requires-python = ">=3.10"
# dependencies = ["requests"]
# ///
"""Generate high-quality images via bytedance-seed/seedream-4.5 (high-tier).

IMPORTANT: Use only when explicitly requested by board or manager.
Default to generate-image-low-flux for all drafts and iterations.

Usage:
    uv run python generate_image.py --prompt "A professional hero image" --output output/final.png
    uv run python generate_image.py --prompt "..." --aspect 16:9 --size 2K --output output/hero.png
    uv run python generate_image.py --prompt "Refine the colors" --input ref.png --output output/edited.png
    uv run python generate_image.py --prompt "Merge into a single banner" --input a.png b.png --output output/banner.png

Environment:
    OPENROUTER_API_KEY — required
"""
import argparse
import base64
import os
import sys
from pathlib import Path

import requests

MODEL = "bytedance-seed/seedream-4.5"
API_URL = "https://openrouter.ai/api/v1/chat/completions"

VALID_ASPECTS = [
    "1:1", "2:3", "3:2", "3:4", "4:3",
    "9:16", "16:9", "9:21", "21:9",
]
VALID_SIZES = ["0.5K", "1K", "2K", "4K"]


def _encode_image(path):
    """Read an image file and return a base64 data URL."""
    import mimetypes
    p = Path(path)
    if not p.exists():
        print(f"[ERROR] Input image not found: {path}", file=sys.stderr)
        sys.exit(1)
    mime = mimetypes.guess_type(str(p))[0] or "image/png"
    b64 = base64.b64encode(p.read_bytes()).decode()
    return f"data:{mime};base64,{b64}"


def generate(prompt, aspect_ratio=None, image_size=None, input_images=None):
    """Call OpenRouter SeedDream and return base64 data URL, or exit on error."""
    api_key = os.environ.get("OPENROUTER_API_KEY") or os.environ.get("OPENROUTER_API")
    if not api_key:
        print("[ERROR] OPENROUTER_API_KEY not set", file=sys.stderr)
        sys.exit(1)

    # Build message content — text first, then any input images
    if input_images:
        content = [{"type": "text", "text": prompt}]
        for img_path in input_images:
            content.append({
                "type": "image_url",
                "image_url": {"url": _encode_image(img_path)},
            })
        messages = [{"role": "user", "content": content}]
    else:
        messages = [{"role": "user", "content": prompt}]

    payload = {
        "model": MODEL,
        "messages": messages,
    }

    image_config = {}
    if aspect_ratio:
        image_config["aspect_ratio"] = aspect_ratio
    if image_size:
        image_config["image_size"] = image_size
    if image_config:
        payload["image_config"] = image_config

    resp = requests.post(
        API_URL,
        headers={"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"},
        json=payload,
        timeout=180,
    )

    if resp.status_code == 402:
        print("[ERROR] Insufficient OpenRouter credits. Add credits at https://openrouter.ai/settings/credits", file=sys.stderr)
        sys.exit(1)
    if resp.status_code != 200:
        print(f"[ERROR] API returned {resp.status_code}: {resp.text}", file=sys.stderr)
        sys.exit(1)

    data = resp.json()
    message = data["choices"][0]["message"]

    # Try message.images first, then content parts
    images = message.get("images", [])
    if images:
        img_entry = images[0]
        if isinstance(img_entry, dict):
            url = (img_entry.get("image_url") or {}).get("url") or img_entry.get("url")
        else:
            url = img_entry
        if url:
            return url

    # Fallback: check content parts
    content = message.get("content")
    if isinstance(content, list):
        for part in content:
            if isinstance(part, dict) and part.get("type") in ("image_url", "image"):
                url = (part.get("image_url") or {}).get("url") or part.get("url")
                if url:
                    return url

    print("[ERROR] No images in response", file=sys.stderr)
    sys.exit(1)


def save_image(data_url, output_path):
    b64 = data_url.split(",", 1)[1] if "," in data_url else data_url
    img_bytes = base64.b64decode(b64)
    out = Path(output_path)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_bytes(img_bytes)
    return str(out.resolve())


def main():
    parser = argparse.ArgumentParser(description=f"Generate images with {MODEL} (high-tier)")
    parser.add_argument("--prompt", required=True, help="Image generation prompt")
    parser.add_argument("--input", nargs="+", metavar="IMAGE", help="One or more input images for editing/composition")
    parser.add_argument("--aspect", choices=VALID_ASPECTS, help="Aspect ratio (e.g. 16:9)")
    parser.add_argument("--size", choices=VALID_SIZES, default="1K", help="Image size (default: 1K)")
    parser.add_argument("--output", default="output/generated.png", help="Output file path")
    args = parser.parse_args()

    mode = "Editing" if args.input else "Generating"
    print(f"{mode} with {MODEL} (HIGH-TIER — size={args.size})...")
    data_url = generate(args.prompt, aspect_ratio=args.aspect, image_size=args.size, input_images=args.input)
    saved = save_image(data_url, args.output)
    print(f"Image saved to: {saved}")


if __name__ == "__main__":
    main()
