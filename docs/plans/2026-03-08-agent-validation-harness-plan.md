# Agent Validation Harness Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Build a local Python harness that runs the consulting-agent validation scenarios against the real local agent runtimes and saves reviewable result artifacts.

**Architecture:** Add a small script that reads private scenario prompts, loads the corresponding local agent config, selects the existing Mission Control runner through `ExecutionEngine`, and writes one result artifact per run. Keep execution logic inside reusable helpers so the script can later back a pytest wrapper if needed.

**Tech Stack:** Python, argparse, PyYAML, existing `mc.application.execution` runtime, local `~/.nanobot` agent/scenario directories

---

### Task 1: Inspect and codify the execution seam

**Files:**
- Modify: `docs/plans/2026-03-08-agent-validation-harness-design.md`
- Create: `scripts/run_agent_validation.py`

**Step 1: Write the execution helper signature**

Define the helper interface in the script for:
- loading agent config
- extracting scenario input text
- building `ExecutionRequest`
- rendering a result artifact

**Step 2: Run a syntax check stub**

Run: `python3 -m py_compile scripts/run_agent_validation.py`
Expected: PASS once the script skeleton is in place

**Step 3: Write minimal implementation**

Add the basic script skeleton, argument parsing, and helper function stubs.

**Step 4: Run syntax check again**

Run: `python3 -m py_compile scripts/run_agent_validation.py`
Expected: PASS

### Task 2: Implement scenario and agent loading

**Files:**
- Modify: `scripts/run_agent_validation.py`

**Step 1: Add agent/scenario loading helpers**

Implement:
- agent config validation via existing YAML validator
- scenario file lookup
- fenced `Input de Teste` extraction

**Step 2: Run syntax check**

Run: `python3 -m py_compile scripts/run_agent_validation.py`
Expected: PASS

**Step 3: Add explicit failure messages**

Surface actionable errors for:
- missing scenario file
- missing agent directory
- invalid YAML config
- missing input block

**Step 4: Run one dry parse**

Run: `python3 scripts/run_agent_validation.py offer-strategist --dry-run`
Expected: prints parsed scenario and runner metadata without executing provider calls

### Task 3: Wire the real execution runtime

**Files:**
- Modify: `scripts/run_agent_validation.py`

**Step 1: Build `ExecutionRequest` from local config**

Use:
- `RunnerType.CLAUDE_CODE` when model is `cc/...`
- `RunnerType.NANOBOT` otherwise

**Step 2: Execute through `ExecutionEngine`**

Use the existing strategies rather than creating a custom runtime path.

**Step 3: Run a real single-agent execution**

Run: `python3 scripts/run_agent_validation.py offer-strategist`
Expected: one result artifact written with either real output or a provider/runtime error captured in the file

**Step 4: Adjust runtime edge cases**

Handle any request-field gaps discovered during the first real execution.

### Task 4: Persist result artifacts cleanly

**Files:**
- Modify: `scripts/run_agent_validation.py`

**Step 1: Add result directory and file writer**

Write Markdown artifacts under:
- `~/.nanobot/private/knowledge-validation/results/<timestamp>/index.md`
- `~/.nanobot/private/knowledge-validation/results/<timestamp>/<agent>.md`

**Step 2: Include enough metadata for review**

Persist:
- timestamp
- agent
- runner
- status
- duration
- source scenario path
- prompt
- output/error

**Step 3: Run a real single-agent execution again**

Run: `python3 scripts/run_agent_validation.py offer-strategist`
Expected: result file exists and contains prompt plus output/error

### Task 5: Run the six-agent validation batch

**Files:**
- Modify: `scripts/run_agent_validation.py` if needed

**Step 1: Add multi-agent iteration**

Support:
- one agent argument
- many agent arguments
- `--all` for the consulting-agent set

**Step 2: Run the full batch**

Run: `python3 scripts/run_agent_validation.py --all`
Expected: six result files plus an index file

**Step 3: Verify outputs**

Inspect generated artifacts and confirm each agent produced either:
- a runtime output
- or a clearly captured actionable failure

### Task 6: Report results with evidence

**Files:**
- none required unless the implementation reveals a repo bug worth fixing

**Step 1: Summarize the run**

Report:
- which agents ran
- which succeeded
- which failed and why
- where the artifacts were written

**Step 2: Keep the next action tight**

Recommend whether to:
- tune prompts
- tune skills/memory
- or fix runtime/provider configuration
