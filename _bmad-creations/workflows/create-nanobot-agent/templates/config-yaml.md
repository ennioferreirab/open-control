# Config YAML Template

Use this template to generate the final `config.yaml`. Fill all placeholders.

```yaml
name: {agent-name}
display_name: "{agent-display-name}"
role: "{agent-role}"
prompt: |
  {agent-prompt}
skills:
{agent-skills-list}
model: {agent-model}
```

## SOUL.md Template (generate separately if needed)

```markdown
# Soul

I am {agent-display-name}, a nanobot agent.

## Role
{agent-role}

## Personality
{agent-personality-traits}

## Values
{agent-values}

## Communication Style
{agent-communication-style}
```

## Notes for generation

- `{agent-skills-list}`: format each skill as `  - skill-name` (2-space indent, dash, space)
- If `model` is the system default (user chose to omit), remove the `model:` line entirely
- If `display_name` auto-generates from `name`, remove the `display_name:` line
- `prompt` block: preserve `|` literal block scalar, indent content 2 spaces
