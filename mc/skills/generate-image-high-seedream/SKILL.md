---
name: generate-image-high-seedream
description: generate high-quality images using bytedance-seed/seedream-4.5 (high-tier). use ONLY when explicitly requested by board or manager for production/final deliverables.
---

# Generate Image — High Tier (`bytedance-seed/seedream-4.5`)

Generate high-quality images via OpenRouter using the SeedDream 4.5 model.

**IMPORTANT:** Use this skill **only when the board or your manager explicitly requests high-tier quality**. Default to `generate-image-low-flux` for all drafts and iterations.

## Quick Start — Text to Image

```bash
curl -s -X POST "https://openrouter.ai/api/v1/chat/completions" \
  -H "Authorization: Bearer $OPENROUTER_API_KEY" \
  -H "Content-Type: application/json" \
  -d '{
    "model": "bytedance-seed/seedream-4.5",
    "messages": [{"role": "user", "content": "A minimalist logo on white background"}]
  }' | python3 -c "
import json, sys, base64; from pathlib import Path
data = json.load(sys.stdin)
url = data['choices'][0]['message']['images'][0]['image_url']['url']
Path('output').mkdir(exist_ok=True)
Path('output/generated.png').write_bytes(base64.b64decode(url.split(',',1)[1]))
print('Saved to output/generated.png')
"
```

## With Aspect Ratio and Size

Add `image_config` to the payload for aspect ratio and resolution control:

```bash
curl -s -X POST "https://openrouter.ai/api/v1/chat/completions" \
  -H "Authorization: Bearer $OPENROUTER_API_KEY" \
  -H "Content-Type: application/json" \
  -d '{
    "model": "bytedance-seed/seedream-4.5",
    "messages": [{"role": "user", "content": "Brand hero image, dark navy background"}],
    "image_config": {"aspect_ratio": "16:9", "image_size": "2K"}
  }' | python3 -c "
import json, sys, base64; from pathlib import Path
data = json.load(sys.stdin)
url = data['choices'][0]['message']['images'][0]['image_url']['url']
Path('output').mkdir(exist_ok=True)
Path('output/hero.png').write_bytes(base64.b64decode(url.split(',',1)[1]))
print('Saved to output/hero.png')
"
```

## With Input Image (Editing)

Encode the input image as a base64 data URL and pass it as an `image_url` content part:

```bash
IMG_B64=$(base64 -i reference.png)
curl -s -X POST "https://openrouter.ai/api/v1/chat/completions" \
  -H "Authorization: Bearer $OPENROUTER_API_KEY" \
  -H "Content-Type: application/json" \
  -d "$(python3 -c "
import json
payload = {
    'model': 'bytedance-seed/seedream-4.5',
    'messages': [{'role': 'user', 'content': [
        {'type': 'text', 'text': 'Refine the colors and lighting'},
        {'type': 'image_url', 'image_url': {'url': 'data:image/png;base64,$(cat <<< $IMG_B64)'}}
    ]}],
    'image_config': {'image_size': '2K'}
}
print(json.dumps(payload))
")" | python3 -c "
import json, sys, base64; from pathlib import Path
data = json.load(sys.stdin)
url = data['choices'][0]['message']['images'][0]['image_url']['url']
Path('output').mkdir(exist_ok=True)
Path('output/refined.png').write_bytes(base64.b64decode(url.split(',',1)[1]))
print('Saved to output/refined.png')
"
```

## With Multiple Input Images

Same approach — add multiple `image_url` content parts:

```bash
python3 -c "
import json, base64, sys, os, requests
from pathlib import Path

prompt = 'Merge these into a single banner'
input_files = ['logo.png', 'hero.png', 'badge.png']
output_file = 'output/banner.png'

content = [{'type': 'text', 'text': prompt}]
for f in input_files:
    b64 = base64.b64encode(Path(f).read_bytes()).decode()
    content.append({'type': 'image_url', 'image_url': {'url': f'data:image/png;base64,{b64}'}})

resp = requests.post('https://openrouter.ai/api/v1/chat/completions',
    headers={'Authorization': f'Bearer {os.environ[\"OPENROUTER_API_KEY\"]}', 'Content-Type': 'application/json'},
    json={'model': 'bytedance-seed/seedream-4.5', 'messages': [{'role': 'user', 'content': content}],
          'image_config': {'aspect_ratio': '16:9', 'image_size': '2K'}},
    timeout=180)

data = resp.json()
if 'error' in data:
    print(f'ERROR: {data[\"error\"]}', file=sys.stderr); sys.exit(1)
url = data['choices'][0]['message']['images'][0]['image_url']['url']
Path(output_file).parent.mkdir(parents=True, exist_ok=True)
Path(output_file).write_bytes(base64.b64decode(url.split(',',1)[1]))
print(f'Saved to {output_file}')
"
```

Requires `OPENROUTER_API_KEY` in environment.

## Parameters

| Parameter | Values | Default | Notes |
|-----------|--------|---------|-------|
| `model` | `bytedance-seed/seedream-4.5` | required | Always use this exact model ID |
| `image_config.aspect_ratio` | 1:1, 16:9, 9:16, 4:3, 3:4, 3:2, 2:3 | model default | Optional |
| `image_config.image_size` | 0.5K, 1K, 2K, 4K | 1K | Optional |

**IMPORTANT:** Do NOT include `modalities` in the payload. SeedDream returns images by default — adding `"modalities": ["image", "text"]` causes a 404 error.

## Response Format

```json
{
  "choices": [{
    "message": {
      "images": [{
        "type": "image_url",
        "image_url": {"url": "data:image/jpeg;base64,..."}
      }]
    }
  }]
}
```

Extract: `choices[0].message.images[0].image_url.url` — base64 data URL.

## Error Handling

- **HTTP 402 / Insufficient credits:** Do NOT retry or switch models. Ask user to add credits at `https://openrouter.ai/settings/credits`.
- **HTTP 404 "No endpoints found":** You are sending `modalities` in the payload. Remove it.
- **HTTP 401:** API key missing or invalid.
- **HTTP 429:** Wait a few seconds, retry once.

## Aspect Ratios by Use Case

| Use case | Ratio |
|----------|-------|
| Logo / square post | 1:1 |
| Instagram story / TikTok | 9:16 |
| Presentation hero | 16:9 |
| Portrait / poster | 2:3 |
| Blog / landscape | 3:2 |

## Design Guidance

For prompt engineering and brand consistency, read [references/design-guidelines.md](references/design-guidelines.md).
