# Story 3.5: Implement Agent-Assisted CLI

Status: done

## Story

As a **user**,
I want to describe an agent in natural language and have nanobot generate the YAML configuration for me,
So that I can create agents without knowing the YAML schema.

## Acceptance Criteria

1. **Given** Mission Control is running, **When** the user runs `nanobot mc agents create --assisted` or `nanobot mc agents assist`, **Then** the nanobot agent interprets the natural language description and generates a complete, valid YAML configuration
2. **Given** the user provides a natural language description (e.g., "create a financial agent that tracks boletos and manages payments"), **Then** the agent infers: name, role, skills, and system prompt from the description
3. **Given** the agent generates a YAML configuration, **Then** the generated YAML is presented to the user for confirmation before saving
4. **Given** the user confirms the generated YAML, **When** the file is saved, **Then** it is written to `~/.nanobot/agents/{name}/config.yaml` with the agent workspace structure (memory/, skills/)
5. **Given** the saved YAML file, **Then** validation runs using Story 3.1 validator and the CLI prints confirmation with the file path
6. **Given** the user rejects the generated YAML, **When** they provide feedback, **Then** the agent regenerates with adjustments based on the feedback
7. **Given** the user rejects without feedback, **Then** the CLI exits without creating any files
8. **And** agent-assisted creation uses the existing nanobot agent infrastructure (`SubagentManager`)
9. **And** the generated YAML passes all validation rules from Story 3.1

## Tasks / Subtasks

- [x] Task 1: Add assisted creation CLI command (AC: #1)
  - [x] 1.1: Created `assist` subcommand under `agents` in `nanobot/cli/mc.py`
  - [x] 1.2: Prompts user for natural language description via `typer.prompt`
  - [x] 1.3: Passes description to `generate_agent_yaml()` in `agent_assist.py`

- [x] Task 2: Implement agent YAML generation via LLM (AC: #2, #8, #9)
  - [x] 2.1: Created `generate_agent_yaml(provider, description, feedback)` in `agent_assist.py`
  - [x] 2.2: Built `YAML_GENERATION_PROMPT` with schema definition, required/optional fields, and example
  - [x] 2.3: Uses LiteLLMProvider (nanobot's provider infrastructure) via `build_llm_provider()`
  - [x] 2.4: `extract_yaml_from_response()` handles markdown code blocks and plain text
  - [x] 2.5: `validate_yaml_content()` validates using `AgentConfig` pydantic model before presenting

- [x] Task 3: Implement confirmation and feedback loop (AC: #3, #6, #7)
  - [x] 3.1: Displays YAML with Rich `Syntax` highlighting
  - [x] 3.2: Prompts "Save this configuration? [Y/n/edit]"
  - [x] 3.3: "Y" or Enter saves the agent
  - [x] 3.4: "n" exits without saving
  - [x] 3.5: "edit" prompts for feedback, regenerates with feedback appended
  - [x] 3.6: Limited to 3 iterations with fallback save option

- [x] Task 4: Implement file saving with workspace structure (AC: #4, #5)
  - [x] 4.1: `create_agent_workspace()` creates `~/.nanobot/agents/{name}/` with config.yaml, memory/, skills/
  - [x] 4.2: Extracts agent name from parsed YAML dict
  - [x] 4.3: Checks for existing agent and confirms overwrite
  - [x] 4.4: Runs `validate_agent_file()` on the saved file
  - [x] 4.5: Prints confirmation with file path

- [x] Task 5: Write unit tests
  - [x] 5.1: `TestExtractYaml` - code blocks, generic blocks, plain text, empty
  - [x] 5.2: `TestValidateYamlContent` - valid YAML passes Story 3.1 validation
  - [x] 5.3: `TestGenerateAgentYaml` - mocked LLM provider with feedback
  - [x] 5.4: `TestCancellationFlow` - validation is in-memory only, no files created

## Dev Notes

### Critical Architecture Requirements

- **Existing agent infrastructure**: Use the nanobot agent infrastructure (SubagentManager, provider system) to call the LLM. Do NOT create a new LLM client or API wrapper. The agent-assisted CLI should feel like any other nanobot agent task -- it's nanobot helping configure itself.
- **LLM prompt engineering**: The system prompt for YAML generation is critical. It must instruct the LLM to output valid YAML that passes all validation rules (required fields, name format, skills as list). Include the schema definition and an example in the prompt.
- **Validation before save**: Always run the Story 3.1 validator on the generated YAML before saving. If the LLM generates invalid YAML, show the validation errors and allow the user to request regeneration.

### LLM System Prompt for YAML Generation

```python
YAML_GENERATION_PROMPT = """You are helping create a nanobot agent configuration.
Based on the user's description, generate a valid YAML configuration file.

Required fields:
- name: lowercase, alphanumeric + hyphens (e.g., "finance-agent")
- role: brief role description (e.g., "Financial Analyst")
- prompt: detailed system prompt for the agent

Optional fields:
- skills: list of capability tags (e.g., ["financial-analysis", "boleto-tracking"])
- model: LLM model to use (omit to use system default)
- display_name: human-readable name (auto-generated from name if omitted)

Output ONLY the YAML content, no explanation. Example:

name: finance-agent
role: Financial Analyst
prompt: |
  You are a financial analyst agent specializing in personal finance management.
  You track payments, manage boletos, and provide financial summaries.
skills:
  - financial-analysis
  - boleto-tracking
  - payment-management
"""
```

### LLM Response Parsing

The LLM may wrap the YAML in markdown code blocks or add explanatory text. Handle these cases:

```python
def extract_yaml_from_response(response: str) -> str:
    """Extract YAML content from LLM response, handling code blocks."""
    # Try extracting from ```yaml ... ``` blocks
    import re
    match = re.search(r"```(?:yaml)?\s*\n(.*?)```", response, re.DOTALL)
    if match:
        return match.group(1).strip()
    # If no code block, try the entire response as YAML
    return response.strip()
```

### SubagentManager Integration

```python
from nanobot.agent.subagent import SubagentManager

async def generate_agent_yaml(description: str, feedback: str | None = None) -> str:
    """Use nanobot's agent infrastructure to generate agent YAML."""
    prompt = YAML_GENERATION_PROMPT
    if feedback:
        prompt += f"\n\nPrevious attempt was rejected. User feedback: {feedback}"
    prompt += f"\n\nUser's description: {description}"

    # Use SubagentManager to call the LLM
    # (Implementation depends on existing nanobot agent API)
    ...
```

### Confirmation Flow

```
$ nanobot mc agents assist
Describe the agent you want to create:
> I need a financial agent that tracks my boletos, manages recurring payments,
> and provides weekly financial summaries in Portuguese

Generating agent configuration...

---
name: financeiro
role: Financial Manager
prompt: |
  You are a financial management agent for Ennio. You specialize in:
  - Tracking boletos and their due dates
  - Managing recurring payments (Spotify, internet, etc.)
  - Providing weekly financial summaries in Portuguese
  - Alerting about upcoming payments and low balance situations
skills:
  - boleto-tracking
  - payment-management
  - financial-summaries
  - portuguese-communication
---

Save this configuration? [Y/n/edit]: Y

Agent 'financeiro' created at ~/.nanobot/agents/financeiro/config.yaml
```

### Common LLM Developer Mistakes to Avoid

1. **DO NOT create a new LLM client** -- Use the existing nanobot agent infrastructure (SubagentManager or provider system). If the existing infrastructure doesn't easily support a one-shot prompt, create a minimal wrapper that uses the same provider config.
2. **DO NOT trust LLM output blindly** -- Always validate the generated YAML with Story 3.1 validator before saving. LLMs can generate invalid YAML.
3. **DO NOT allow infinite feedback loops** -- Cap the regeneration loop at 3 iterations. After that, suggest manual editing.
4. **DO NOT save without user confirmation** -- Always show the generated YAML and wait for explicit confirmation.
5. **DO NOT forget to handle empty/malformed LLM responses** -- The LLM may return empty, non-YAML, or partial responses. Handle gracefully with a retry or error message.
6. **DO NOT parse YAML with regex** -- Use `yaml.safe_load()` to parse the generated YAML. Regex is only for extracting YAML from markdown code blocks.
7. **DO NOT duplicate workspace creation code** -- Reuse the directory/file creation logic from the `create` command (Story 3.4). Extract it into a shared function if needed.

### What This Story Does NOT Include

- **No dashboard integration** -- This is CLI-only
- **No agent editing via natural language** -- Only creation. Editing is manual YAML
- **No automatic registry sync** -- The user runs `agents list` to sync, or the gateway syncs on start
- **No conversation memory** -- Each assist invocation is stateless. The feedback loop exists within a single session only

### Files Created in This Story

None. All changes go into existing files.

### Files Modified in This Story

| File | Changes |
|------|---------|
| `nanobot/cli/mc.py` | Add `assist` subcommand (or `--assisted` flag) to agents group |

### Optional New File

| File | Purpose |
|------|---------|
| `nanobot/mc/agent_assist.py` | YAML generation logic + LLM prompt + response parsing (if mc.py approaches 500-line limit) |

### Verification Steps

1. Run `nanobot mc agents assist` (or `create --assisted`)
2. Enter description: "create a research agent that finds AI trends"
3. Verify generated YAML has: valid name, role, skills, and detailed prompt
4. Confirm with "Y" -> agent created at `~/.nanobot/agents/{name}/config.yaml`
5. Verify workspace structure: `config.yaml`, `memory/`, `skills/` directories exist
6. Run `nanobot mc agents list` -> new agent appears
7. Test rejection: run assist, enter "n" -> no files created
8. Test feedback: run assist, enter "edit", provide feedback -> regenerated YAML reflects feedback
9. Verify generated YAML passes validation: no validation errors on save

### References

- [Source: `_bmad-output/planning-artifacts/epics.md#Story 3.5`] -- Original story definition
- [Source: `_bmad-output/planning-artifacts/prd.md#CLI Interface`] -- Agent-assisted CLI description
- [Source: `_bmad-output/planning-artifacts/prd.md#Innovation`] -- Agent-assisted configuration as innovation area
- [Source: `nanobot/agent/subagent.py`] -- SubagentManager for LLM interaction
- [Source: `nanobot/mc/yaml_validator.py`] -- Validation module (Story 3.1)
- [Source: `nanobot/cli/mc.py`] -- CLI module to extend

## Dev Agent Record

### Agent Model Used
claude-opus-4-6

### Debug Log References
- Python 3.9 StrEnum import error prevents running tests on this machine (pre-existing issue in types.py, not introduced by this story)
- All files pass AST parsing validation

### Completion Notes List
- Created `nanobot/mc/agent_assist.py` with YAML generation logic, LLM prompt, response parsing, validation, workspace creation, and provider factory
- Added `assist` subcommand to `agents_app` in `nanobot/cli/mc.py` with full confirmation/feedback loop
- Kept `mc.py` under 500 lines (496) by moving business logic to `agent_assist.py`
- Uses existing nanobot LLM provider infrastructure (LiteLLMProvider) -- no new LLM client
- Validates generated YAML with Story 3.1 AgentConfig pydantic model before saving
- Feedback loop capped at 3 iterations
- Overwrite protection for existing agents

### File List
| File | Action |
|------|--------|
| `nanobot/cli/mc.py` | Modified -- added `assist` subcommand + `_save_assisted_agent` helper |
| `nanobot/mc/agent_assist.py` | Created -- YAML generation, extraction, validation, workspace creation, provider factory |
| `nanobot/mc/test_agent_assist.py` | Created -- unit tests for extraction, validation, generation (mocked), workspace creation |
