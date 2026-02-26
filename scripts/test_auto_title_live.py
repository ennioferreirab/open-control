#!/usr/bin/env python3
"""
Live diagnostic for auto-title generation.

Connects to real Convex + real LLM provider, runs generate_auto_title,
and prints step-by-step what happened.

Run:
    uv run python scripts/test_auto_title_live.py
"""

import asyncio
import json
import sys
import os
from pathlib import Path

# Ensure project root is in path
sys.path.insert(0, str(Path(__file__).parent.parent))


SAMPLE_DESCRIPTION = (
    "Poemas curtos revelam a força de dizer muito em tão poucas linhas. "
    "São versos que traduzem emoções profundas, despertam memórias e lembram "
    "que a beleza pode morar no simples. Entre amor, saudade e esperança, "
    "cada palavra abre espaço para sentir mais e compreender melhor o próprio coração."
)


async def main() -> None:
    print("=" * 60)
    print("Auto-Title Live Diagnostic")
    print("=" * 60)

    # ── 1. Resolve Convex URL ──────────────────────────────────
    from nanobot.mc.gateway import _resolve_convex_url
    convex_url = _resolve_convex_url()
    if not convex_url:
        print("FAIL  Convex URL not found.")
        print("      Set CONVEX_URL env var or check dashboard/.env.local")
        sys.exit(1)
    print(f"OK    Convex URL: {convex_url}")

    # ── 2. Connect bridge ──────────────────────────────────────
    from nanobot.mc.bridge import ConvexBridge
    admin_key = os.environ.get("CONVEX_ADMIN_KEY")
    bridge = ConvexBridge(convex_url, admin_key)
    print(f"OK    Bridge connected (admin_key={'set' if admin_key else 'not set'})")

    # ── 3. Read model_tiers setting ────────────────────────────
    print("\n── Model Tier Settings ──────────────────────────────")
    raw_tiers = bridge.query("settings:get", {"key": "model_tiers"})
    if not raw_tiers:
        print("WARN  model_tiers not configured in Settings.")
        print("      Auto-title will use the default model (fallback).")
        low_model = None
    else:
        tiers = json.loads(raw_tiers)
        low_model = tiers.get("standard-low") or None
        print(f"      standard-low  : {low_model or '(not set)'}")
        print(f"      standard-medium: {tiers.get('standard-medium', '(not set)')}")
        print(f"      standard-high : {tiers.get('standard-high', '(not set)')}")
        if not low_model:
            print("WARN  standard-low not configured — will use default model.")

    # ── 4. Resolve actual provider ─────────────────────────────
    print("\n── Provider Resolution ─────────────────────────────")
    from nanobot.mc.provider_factory import create_provider
    try:
        provider, resolved_model = create_provider(model=low_model)
        print(f"OK    Provider: {type(provider).__name__}")
        print(f"OK    Resolved model: {resolved_model}")
    except Exception as e:
        print(f"FAIL  create_provider failed: {e}")
        sys.exit(1)

    # ── 5. Call generate_auto_title ────────────────────────────
    print("\n── Auto-Title Generation ───────────────────────────")
    print(f"      Description ({len(SAMPLE_DESCRIPTION)} chars):")
    print(f"      \"{SAMPLE_DESCRIPTION[:80]}...\"")

    from nanobot.mc.orchestrator import generate_auto_title
    title = await generate_auto_title(bridge, SAMPLE_DESCRIPTION)

    print()
    if title:
        print(f"OK    Generated title: \"{title}\"")
    else:
        print("FAIL  generate_auto_title returned None.")
        print("      Check nanobot MC logs for details.")
        sys.exit(1)

    # ── 6. Verify updateTitle mutation (dry-run) ───────────────
    print("\n── Convex Mutation (dry-run check) ─────────────────")
    print("      updateTitle mutation would be called with:")
    print(f"      task_id = <task_id>")
    print(f"      title   = \"{title}\"")
    print("      (Skipping actual mutation — no task_id in diagnostic)")

    print("\n" + "=" * 60)
    print("RESULT: Auto-title generation works correctly.")
    print(f"        Model used   : {resolved_model}")
    print(f"        Title output : \"{title}\"")
    if not low_model:
        print("        NOTE: Used default model (standard-low not configured).")
        print("              Configure it in Settings > Model Tier Settings for lower cost.")
    print("=" * 60)


if __name__ == "__main__":
    asyncio.run(main())
