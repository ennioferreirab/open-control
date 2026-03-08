# Codex Model Benchmark Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Switch the six consulting agents to `openai-codex/gpt-5.4`, run the validation suite with `reasoning_level=medium`, and compare the new outputs against the existing Claude Code baseline.

**Architecture:** Keep the agent prompts, skills, and scenarios unchanged so the benchmark isolates model/runtime changes. Extend the local validation harness with a `--reasoning-level` override, then use it to produce a new run directory for the Codex batch and compare those artifacts to the March 8 baseline.

**Tech Stack:** Python, pytest, existing Mission Control execution runtime, local `~/.nanobot` agent configs and validation artifacts

---

### Task 1: Add harness coverage for reasoning override

**Files:**
- Create: `tests/test_run_agent_validation.py`
- Modify: `scripts/run_agent_validation.py`

**Step 1: Write the failing test**

Add tests that assert the harness accepts `--reasoning-level medium` and passes that value into the built `ExecutionRequest`.

**Step 2: Run test to verify it fails**

Run: `/Users/ennio/Documents/nanobot-ennio/.venv/bin/python -m pytest /Users/ennio/Documents/nanobot-ennio/tests/test_run_agent_validation.py -q`
Expected: FAIL because the script does not yet accept or propagate reasoning level.

**Step 3: Write minimal implementation**

Add the CLI flag, thread the override into `build_request`, and include it in the result metadata.

**Step 4: Run test to verify it passes**

Run: `/Users/ennio/Documents/nanobot-ennio/.venv/bin/python -m pytest /Users/ennio/Documents/nanobot-ennio/tests/test_run_agent_validation.py -q`
Expected: PASS

### Task 2: Switch the six agents to Codex

**Files:**
- Modify: `~/.nanobot/agents/offer-strategist/config.yaml`
- Modify: `~/.nanobot/agents/sales-revops/config.yaml`
- Modify: `~/.nanobot/agents/contracts-risk/config.yaml`
- Modify: `~/.nanobot/agents/delivery-systems/config.yaml`
- Modify: `~/.nanobot/agents/marketing-copy/config.yaml`
- Modify: `~/.nanobot/agents/finance-pricing/config.yaml`

**Step 1: Update the model field**

Replace the existing `cc/...` model strings with `openai-codex/gpt-5.4`.

**Step 2: Verify config integrity**

Run the harness dry-run for one agent to confirm the new model is loaded and routed through the non-CC runtime path.

### Task 3: Run the Codex benchmark

**Files:**
- none required unless runtime issues appear

**Step 1: Run one agent first**

Run: `/Users/ennio/Documents/nanobot-ennio/.venv/bin/python /Users/ennio/Documents/nanobot-ennio/scripts/run_agent_validation.py offer-strategist --reasoning-level medium`
Expected: result artifact written successfully.

**Step 2: Run the full six-agent batch**

Run: `/Users/ennio/Documents/nanobot-ennio/.venv/bin/python /Users/ennio/Documents/nanobot-ennio/scripts/run_agent_validation.py --all --reasoning-level medium`
Expected: six result files plus a new `index.md`.

### Task 4: Compare against the baseline

**Files:**
- none required

**Step 1: Inspect baseline and Codex run artifacts**

Compare the existing baseline run at `/Users/ennio/.nanobot/private/knowledge-validation/results/20260308-130537/` with the new Codex run.

**Step 2: Score by agent**

Use the scenario rubrics to judge which output is stronger on structure, scope discipline, actionability, and escalation.

**Step 3: Summarize winner and tradeoffs**

Report which model performed better overall and where each model was stronger or weaker.
