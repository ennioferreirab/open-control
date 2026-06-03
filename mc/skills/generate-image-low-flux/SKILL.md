---
name: generate-image-low-flux
description: generate images using black-forest-labs/flux.2-klein-4b (low-tier, default). use for ALL drafts, explorations, and testing. fast and cost-efficient.
---

# Generate Image — Low Tier (`black-forest-labs/flux.2-klein-4b`)

Generate images via OpenRouter using the low-cost Flux model.

**Use for:** ALL drafts, explorations, iterations, and testing.
**Do NOT use for:** final production deliverables — use `generate-image-high-seedream` only when explicitly requested by board/manager.

## Quick Start — Text to Image

```bash
curl -s -X POST "https://openrouter.ai/api/v1/chat/completions" \
  -H "Authorization: Bearer $OPENROUTER_API_KEY" \
  -H "Content-Type: application/json" \
  -d '{
    "model": "black-forest-labs/flux.2-klein-4b",
    "messages": [{"role": "user", "content": "A minimalist logo on white background"}]
  }' | python3 -c "
import json, sys, base64; from pathlib import Path
data = json.load(sys.stdin)
url = data['choices'][0]['message']['images'][0]['image_url']['url']
Path('output').mkdir(exist_ok=True)
Path('output/draft.png').write_bytes(base64.b64decode(url.split(',',1)[1]))
print('Saved to output/draft.png')
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
    'model': 'black-forest-labs/flux.2-klein-4b',
    'messages': [{'role': 'user', 'content': [
        {'type': 'text', 'text': 'Make the background blue'},
        {'type': 'image_url', 'image_url': {'url': 'data:image/png;base64,$(cat <<< $IMG_B64)'}}
    ]}]
}
print(json.dumps(payload))
")" | python3 -c "
import json, sys, base64; from pathlib import Path
data = json.load(sys.stdin)
url = data['choices'][0]['message']['images'][0]['image_url']['url']
Path('output').mkdir(exist_ok=True)
Path('output/edited.png').write_bytes(base64.b64decode(url.split(',',1)[1]))
print('Saved to output/edited.png')
"
```

## With Multiple Input Images

Same approach — add multiple `image_url` content parts:

```bash
python3 -c "
import json, base64, sys, os, requests
from pathlib import Path

prompt = 'Combine these into a single composition'
input_files = ['logo.png', 'hero.png', 'badge.png']
output_file = 'output/composed.png'

content = [{'type': 'text', 'text': prompt}]
for f in input_files:
    b64 = base64.b64encode(Path(f).read_bytes()).decode()
    content.append({'type': 'image_url', 'image_url': {'url': f'data:image/png;base64,{b64}'}})

resp = requests.post('https://openrouter.ai/api/v1/chat/completions',
    headers={'Authorization': f'Bearer {os.environ[\"OPENROUTER_API_KEY\"]}', 'Content-Type': 'application/json'},
    json={'model': 'black-forest-labs/flux.2-klein-4b', 'messages': [{'role': 'user', 'content': content}]},
    timeout=120)

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
| `model` | `black-forest-labs/flux.2-klein-4b` | required | Always use this exact model ID |

**IMPORTANT:** Do NOT include `modalities`, `image_config`, or `max_tokens` in the payload for Flux. The model does not support them.

For aspect ratio control with Flux, append the desired ratio to your prompt text (e.g., "A logo, aspect ratio 1:1").

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
- **HTTP 502 Provider error:** Retry once with a shorter/simpler prompt. If it persists, report blocked.
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
