# Phase 8 — Delete the provider Factory and nanobot.providers

Back to [overview.md](overview.md).

## Goal

With no callers left after Phase 7, delete the provider Factory and every `nanobot.providers` import. This collapses the hardest slice of the nanobot extraction (the **subtract-before-you-add** principle: the deletion makes the rest of Track B smaller).

## Changes

- Delete [mc/infrastructure/providers/factory.py](../../../mc/infrastructure/providers/factory.py) (`create_provider`, `list_available_models`) and its package if empty.
- Remove the `nanobot.providers.*` imports it carried: `litellm_provider`, `anthropic_oauth_provider`, `openai_codex_provider`, `custom_provider`, and the `CODEX_MODELS` import (factory.py lines 29, 158, 172, 192, 203 from the investigation).
- Remove the `AnthropicOAuthExpired` catch sites that only existed for the Factory's providers ([mc/contexts/execution/provider_errors.py](../../../mc/contexts/execution/provider_errors.py), [post_processing.py](../../../mc/contexts/execution/post_processing.py), [mc/application/execution/engine.py:52](../../../mc/application/execution/engine.py), [strategies/claude_code.py](../../../mc/application/execution/strategies/claude_code.py)). The ACP harness owns auth now; these error paths move or disappear.
- Remove `title_generation.py`'s re-export of `create_provider` and any now-dead provider tier resolver code ([mc/infrastructure/providers/](../../../mc/infrastructure/providers/)).

## Data structures

- Net removal. No new types.

## Verification

**Static.** `make check`; `uv run pytest`. Grep proves zero `nanobot.providers` references and zero `create_provider` references in `mc/`.

**Runtime.** `make start`. Run a task and an @mention end-to-end; both work without the Factory. The provider layer is gone and nothing in the hot path imported it. Capture in the PR.
