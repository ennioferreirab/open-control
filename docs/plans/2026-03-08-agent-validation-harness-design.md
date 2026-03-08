# Agent Validation Harness Design

## Summary

The repo already has real execution paths for Mission Control agents through
`ExecutionEngine`, `NanobotRunnerStrategy`, and `ClaudeCodeRunnerStrategy`.
What it does not have is a focused way to run the new consulting-agent
validation scenarios from `~/.nanobot/private/knowledge-validation` against the
real agent configs in `~/.nanobot/agents` and persist the outputs for review.

This design adds a local Python harness that exercises those existing runtime
paths without requiring a full Mission Control board workflow.

## Goals

- run a validation scenario against any local agent by name
- use the real runtime path for both nanobot and Claude Code agents
- read canonical scenario prompts from the private validation library
- persist outputs and metadata for later scoring against the rubric
- keep the harness small and isolated from production runtime loops

## Non-Goals

- scoring agent quality automatically in v1
- introducing a new Mission Control backend API
- replacing task/chat execution flows already used by the product
- adding CI gating for real-provider validation runs

## Approaches Considered

### 1. Standalone harness script

Create a script that:
- loads the agent config from `~/.nanobot/agents/<name>/config.yaml`
- loads the scenario from `~/.nanobot/private/knowledge-validation/<name>.md`
- extracts the `Input de Teste` block
- executes the agent through `ExecutionEngine`
- writes a Markdown result artifact under the private validation directory

Pros:
- exercises the real runner stack
- minimal coupling to Convex/board state
- easy to run one agent or all agents

Cons:
- separate from `pytest`

### 2. Real-provider pytest integration

Wrap the same execution flow in parametrized tests.

Pros:
- standard test UX

Cons:
- brittle for local/provider-dependent runs
- harder to use as an exploratory pressure-test workflow

## Decision

Use a standalone harness script first. If it proves stable, we can later add a
thin pytest wrapper around the script's core execution helper.

## Architecture

### Inputs

- private scenario files:
  `~/.nanobot/private/knowledge-validation/<agent>.md`
- local agent configs:
  `~/.nanobot/agents/<agent>/config.yaml`

### Execution flow

1. Parse CLI arguments for one agent or `--all`.
2. Read the scenario file and extract the fenced `Input de Teste` block.
3. Validate the local agent config and determine the runner:
   - `RunnerType.CLAUDE_CODE` when the model is `cc/...`
   - `RunnerType.NANOBOT` otherwise
4. Build an `ExecutionRequest` with:
   - task-style execution
   - scenario prompt as the title payload
   - local agent prompt/model/skills from YAML
5. Execute through `ExecutionEngine`.
6. Persist one Markdown result per agent with:
   - timestamp
   - runner
   - scenario source
   - raw prompt
   - output or error
   - duration

### Output layout

Results live under:
`~/.nanobot/private/knowledge-validation/results/<timestamp>/`

Each agent gets one file:
`<agent>.md`

An optional run index file summarizes statuses for the whole batch.

## Error Handling

- missing scenario file: fail that agent with a clear message
- missing/invalid agent config: fail that agent with validator output
- missing provider auth/config: surface the existing actionable runtime error
- empty response: mark as failed execution, still write a result artifact

## Verification

1. run one known agent first: `offer-strategist`
2. inspect the generated artifact for prompt/output integrity
3. run all six consulting agents in one batch

## Files

- create `scripts/run_agent_validation.py`
- optionally create `tests/mc/test_agent_validation_harness.py` later if the
  harness stabilizes
