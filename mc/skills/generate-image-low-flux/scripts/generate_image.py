#!/usr/bin/env python3
# /// script
# requires-python = ">=3.10"
# dependencies = ["requests"]
# ///
"""Generate images via black-forest-labs/flux.2-klein-4b (low-tier default).

Usage:
    uv run python generate_image.py --prompt "A minimalist logo" --output output/logo.png
    uv run python generate_image.py --prompt "Logo" --aspect 1:1 --output output/logo.png
    uv run python generate_image.py --prompt "Make the background blue" --input ref.png --output output/edited.png
    uv run python generate_image.py --prompt "Combine these into a collage" --input a.png b.png --output output/collage.png

Environment:
    OPENROUTER_API_KEY — required
"""
import argparse
import base64
import os
import sys
from pathlib import Path

import requests

MODEL = "black-forest-labs/flux.2-klein-4b"
API_URL = "https://openrouter.ai/api/v1/chat/completions"

VALID_ASPECTS = [
    "1:1", "2:3", "3:2", "3:4", "4:3",
    "9:16", "16:9", "9:21", "21:9",
]


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


def generate(prompt, aspect_ratio=None, input_images=None):
    """Call OpenRouter Flux and return base64 data URL, or exit on error."""
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

    resp = requests.post(
        API_URL,
        headers={"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"},
        json=payload,
        timeout=120,
    )

    if resp.status_code == 402:
        print("[ERROR] Insufficient OpenRouter credits. Add credits at https://openrouter.ai/settings/credits", file=sys.stderr)
        sys.exit(1)
    if resp.status_code != 200:
        print(f"[ERROR] API returned {resp.status_code}: {resp.text}", file=sys.stderr)
        sys.exit(1)

    data = resp.json()
    message = data["choices"][0]["message"]

    # Flux returns images in message.images[0].image_url.url as base64 data URL
    images = message.get("images", [])
    if not images:
        print("[ERROR] No images in response", file=sys.stderr)
        sys.exit(1)

    img_entry = images[0]
    if isinstance(img_entry, dict):
        url = (img_entry.get("image_url") or {}).get("url") or img_entry.get("url")
    else:
        url = img_entry

    if not url:
        print("[ERROR] Could not extract image URL from response", file=sys.stderr)
        sys.exit(1)

    return url


def save_image(data_url, output_path):
    b64 = data_url.split(",", 1)[1] if "," in data_url else data_url
    img_bytes = base64.b64decode(b64)
    out = Path(output_path)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_bytes(img_bytes)
    return str(out.resolve())


def main():
    parser = argparse.ArgumentParser(description=f"Generate images with {MODEL}")
    parser.add_argument("--prompt", required=True, help="Image generation prompt")
    parser.add_argument("--input", nargs="+", metavar="IMAGE", help="One or more input images for editing/composition")
    parser.add_argument("--aspect", choices=VALID_ASPECTS, help="Aspect ratio (e.g. 16:9). Optional.")
    parser.add_argument("--output", default="output/generated.png", help="Output file path")
    args = parser.parse_args()

    prompt = args.prompt
    if args.aspect:
        prompt = f"{prompt} [aspect ratio: {args.aspect}]"

    mode = "Editing" if args.input else "Generating"
    print(f"{mode} with {MODEL}...")
    data_url = generate(prompt, input_images=args.input)
    saved = save_image(data_url, args.output)
    print(f"Image saved to: {saved}")


if __name__ == "__main__":
    main()
