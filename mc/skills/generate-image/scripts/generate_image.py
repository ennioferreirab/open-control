#!/usr/bin/env python3
"""Generate or edit images via OpenRouter image generation models.

Usage:
    python generate_image.py --prompt "A sunset over mountains" [--quality high|medium] [--aspect RATIO] [--size SIZE] [--output PATH]
    python generate_image.py --prompt "Remove the background" --input photo.jpg [--quality high] [--output PATH]
    python generate_image.py --prompt "Analyze this" --input photo.jpg --quality medium [--output PATH]

Quality tiers:
    high   — Gemini 3.1 Flash Image (production/publication). Sizes: 0.5K, 1K
    medium — Gemini 2.5 Flash Image (reference/analysis, ~50% cheaper). Sizes: 0.5K, 1K.
    IMPORTANT: FOR NOW USE ONLY medium quality because we are in test

Environment:
    OPENROUTER_API_KEY — required
"""
#0.5K, 1K, 2K, 4K.
import argparse
import base64
import os
import sys
from pathlib import Path

import requests

QUALITY_MODELS = {
    "high": "google/gemini-3.1-flash-image-preview",
    "medium": "google/gemini-2.5-flash-image",
}
QUALITY_SIZES = {
    "high": ["0.5K", "1K", "2K", "4K"],
    "medium": ["0.5K", "1K"],
}
API_URL = "https://openrouter.ai/api/v1/chat/completions"

VALID_ASPECTS = [
    "1:1", "2:3", "3:2", "3:4", "4:3",
    "9:16", "16:9", "9:21", "21:9", "1:2",
    "1:4", "4:1", "1:8", "8:1",
]
VALID_SIZES = ["0.5K", "1K", "2K", "4K"]


def build_messages(prompt, input_image=None):
    """Build the messages array, optionally with an input image for editing."""
    if input_image:
        img_path = Path(input_image)
        if not img_path.exists():
            print(f"[ERROR] Input image not found: {input_image}", file=sys.stderr)
            sys.exit(1)
        suffix = img_path.suffix.lower().lstrip(".")
        mime = {
            "jpg": "image/jpeg", "jpeg": "image/jpeg", "png": "image/png",
            "gif": "image/gif", "webp": "image/webp",
        }.get(suffix, f"image/{suffix}")
        b64 = base64.b64encode(img_path.read_bytes()).decode()
        data_url = f"data:{mime};base64,{b64}"
        return [{
            "role": "user",
            "content": [
                {"type": "image_url", "image_url": {"url": data_url}},
                {"type": "text", "text": prompt},
            ],
        }]
    return [{"role": "user", "content": prompt}]


def generate(prompt, model, aspect_ratio=None, image_size=None, input_image=None):
    """Call OpenRouter and return (base64_data_url, text_response).

    Returns (None, None) on failure.
    """
    api_key = os.environ.get("OPENROUTER_API_KEY") or os.environ.get("OPENROUTER_API")
    if not api_key:
        print("[ERROR] OPENROUTER_API_KEY or OPENROUTER_API not set", file=sys.stderr)
        sys.exit(1)

    payload = {
        "model": model,
        "messages": build_messages(prompt, input_image),
        "modalities": ["image", "text"],
        "max_tokens": 4096,
    }

    image_config = {}
    if aspect_ratio:
        image_config["aspect_ratio"] = aspect_ratio
    if image_size:
        image_config["image_size"] = image_size
    if image_config:
        payload["image_config"] = image_config

    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json",
    }

    resp = requests.post(API_URL, headers=headers, json=payload, timeout=120)
    if resp.status_code != 200:
        print(f"[ERROR] API returned {resp.status_code}: {resp.text}", file=sys.stderr)
        return None, None

    data = resp.json()
    choice = data.get("choices", [{}])[0]
    message = choice.get("message", {})

    image_url = None
    text = None

    def _extract_url(obj):
        """Extract a data URL string from various response shapes."""
        if isinstance(obj, str):
            return obj
        if isinstance(obj, dict):
            return obj.get("url") or (obj.get("image_url") or {}).get("url")
        return None

    # Images can be in message.images or inline in content
    images = message.get("images")
    if images and isinstance(images, list):
        image_url = _extract_url(images[0])

    content = message.get("content")
    if isinstance(content, str):
        text = content
    elif isinstance(content, list):
        for part in content:
            if isinstance(part, dict):
                if part.get("type") in ("image_url", "image"):
                    image_url = image_url or _extract_url(part)
                elif part.get("type") == "text":
                    text = part.get("text")

    return image_url, text


def save_image(data_url, output_path):
    """Decode a data URL and save to disk. Returns the saved path."""
    if "," in data_url:
        _, b64_data = data_url.split(",", 1)
    else:
        b64_data = data_url

    img_bytes = base64.b64decode(b64_data)
    out = Path(output_path)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_bytes(img_bytes)
    return str(out.resolve())


def main():
    parser = argparse.ArgumentParser(description="Generate or edit images via OpenRouter")
    parser.add_argument("--prompt", required=True, help="Image generation or editing prompt")
    parser.add_argument(
        "--quality", choices=["high", "medium"], default="high",
        help="Quality tier: high (Gemini 3.1, sizes 0.5K-4K) or medium (Gemini 2.5, sizes 0.5K-1K, ~50%% cheaper). Default: high",
    )
    parser.add_argument(
        "--model", default=None,
        help="Override model ID (ignores --quality)",
    )
    parser.add_argument("--aspect", choices=VALID_ASPECTS, help="Aspect ratio (e.g. 16:9)")
    parser.add_argument("--size", choices=VALID_SIZES, default="1K", help="Image size (default: 1K)")
    parser.add_argument("--input", dest="input_image", help="Input image path for editing")
    parser.add_argument("--output", default="output/generated.png", help="Output file path")
    args = parser.parse_args()

    # Resolve model from quality tier or explicit override
    if args.model:
        model = args.model
    else:
        model = QUALITY_MODELS[args.quality]
        allowed_sizes = QUALITY_SIZES[args.quality]
        if args.size not in allowed_sizes:
            print(
                f"[ERROR] Size '{args.size}' is not available for quality '{args.quality}'. "
                f"Allowed sizes: {', '.join(allowed_sizes)}",
                file=sys.stderr,
            )
            sys.exit(1)

    print(f"Generating with {model} (quality={args.quality}, size={args.size})...")
    image_url, text = generate(
        prompt=args.prompt,
        model=model,
        aspect_ratio=args.aspect,
        image_size=args.size,
        input_image=args.input_image,
    )

    if text:
        print(f"\nModel response: {text}")

    if image_url:
        saved = save_image(image_url, args.output)
        print(f"\nImage saved to: {saved}")
    else:
        print("\n[WARN] No image returned by the model", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()
