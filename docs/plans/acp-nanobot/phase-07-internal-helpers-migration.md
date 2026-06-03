# Phase 7 — Migrate internal one-shot helpers off the Factory

Back to [overview.md](overview.md).

> Contested design. Run the **interrogate** skill (four-model adversarial) before shipping. This is the one phase where "no raw calls" has a real cost and the right per-site answer is not obvious.

## Goal

Remove every remaining caller of the provider Factory, so Phase 8 can delete it. The callers are internal one-shot completions, not agentic tasks, so each needs a deliberate decision rather than a blanket harness spawn.

## Changes

The call sites to migrate (from the investigation, exact lines):

- Auto-title generation — [mc/runtime/orchestrator.py:90](../../../mc/runtime/orchestrator.py), `provider.chat(...)` at line 95.
- Task routing — [mc/contexts/routing/llm_delegator.py:146](../../../mc/contexts/routing/llm_delegator.py).
- Memory consolidation — [mc/memory/consolidation.py:128](../../../mc/memory/consolidation.py) and [mc/memory/service.py:185](../../../mc/memory/service.py).
- LLM post-processing — [mc/contexts/execution/agent_runner.py:78](../../../mc/contexts/execution/agent_runner.py) and [mc/contexts/execution/post_processing.py:290](../../../mc/contexts/execution/post_processing.py).
- The @mention chat reply — [mc/contexts/conversation/chat_handler.py](../../../mc/contexts/conversation/chat_handler.py) (also the known routing bug, fix it here).

**Spike first.** Classify each site into one of three target paths and record the choice:
1. A lightweight utility-harness turn over ACP (a cheap model behind a harness) where an LLM is genuinely needed.
2. Drop the LLM call for a deterministic heuristic where one suffices (a title from the first message, rule-based routing).
3. Fold the call into the task's own harness turn where it is really part of that turn.

Spawning a full coding-agent subprocess per one-line title is the wasteful path; the spike exists to avoid it.

**Recommended per-site shape (pre-spike).**
- @mention chat reply → a normal harness turn. It is a conversational agent turn and belongs behind a harness; routing it here is also the fix for the known @mention bug.
- Memory consolidation → a lightweight ACP utility harness (a thin agent that runs one completion and returns), not a coding agent. The orchestrator stays ACP-uniform; the model call lives inside the harness, so the "no raw calls" rule holds. This is the one internal call substantial enough to justify a model.
- Routing → a deterministic heuristic for now (rule-based on agent capabilities), no model call (the **subtract-before-you-add** principle). The same LLM-option mechanism below could be added later if rules prove insufficient.
- Auto-title → heuristic by default (title from the first message). Plus a **configurable LLM option**: when enabled, it runs one prompt on the configured utility harness at its `low` tier, resolved through that harness's `model_tiers` de-para (Phase 3). Which harness serves title generation is config, not hardcoded.
- LLM post-processing → fold into the task's own harness turn, where the data already is.

The genuine open risk the spike must measure: per-call latency and cost of a utility-harness round-trip versus the old in-process completion. These cheap calls are hot (most tasks get a title and a routing decision), so subprocess and IPC overhead compounds. If it is too high, push more sites onto heuristics.

## Data structures

- A utility-turn helper (if option 1 is chosen for any site) — one entry point that runs a single ACP prompt and returns text, reusing `AcpClient`. Decided once, called from each migrated site.

## Verification

**Static.** `make check`; `uv run pytest`. Grep proves zero `create_provider` / `_make_provider` callers remain.

**Runtime.** `make start`. Exercise each migrated behavior on the real stack: a task gets an auto-title, routing picks an agent, memory consolidates, an @mention gets a reply through the correct path (proving the routing bug is fixed). Reproduce the @mention bug first, then prove it gone on the same surface (TDD red-green). Capture in the PR.
