---
name: reddit-search
description: Use when searching Reddit for community discussions, tool recommendations, developer opinions, OSS project experiences, or market research using the public Reddit JSON API or a Reddit MCP server.
---

# Reddit Search

Search Reddit for community insights, developer recommendations, and real-world experiences with tools or technologies. Two modes: zero-setup public API, or full-featured MCP server.

## Mode A — Public JSON API (Zero Setup)

Reddit exposes a public JSON API at `https://www.reddit.com`. No API key or auth required for read-only searches.

### Search across all of Reddit

```bash
curl -s -A "S&K-Researcher/1.0" \
  "https://www.reddit.com/search.json?q=QUERY&sort=relevance&limit=10&type=link" | \
  python3 -c "
import json,sys
d=json.load(sys.stdin)
for p in d['data']['children']:
    pd = p['data']
    print(f\"r/{pd['subreddit']} | ↑{pd['score']} | {pd['title'][:80]}\")
    print(f\"  https://reddit.com{pd['permalink']}\")
"
```

### Search within a specific subreddit

```bash
curl -s -A "S&K-Researcher/1.0" \
  "https://www.reddit.com/r/SUBREDDIT/search.json?q=QUERY&restrict_sr=on&sort=top&limit=10"
```

### Get top posts from a subreddit

```bash
curl -s -A "S&K-Researcher/1.0" \
  "https://www.reddit.com/r/SUBREDDIT/top.json?t=year&limit=10"
```

### Sort options

| Sort | Use for |
|---|---|
| `relevance` | Finding discussions matching a keyword |
| `top` | Most upvoted (best signal for quality) |
| `new` | Recent activity, latest releases |
| `hot` | Currently active discussions |

### Time filter (`t=`)

`hour`, `day`, `week`, `month`, `year`, `all`

### Key subreddits for S&K research

| Subreddit | Content |
|---|---|
| `r/MachineLearning` | AI/ML research, model releases |
| `r/LocalLLaMA` | Local models, inference tools |
| `r/ClaudeAI` | Claude-specific tools, experiences |
| `r/OpenAI` | GPT, API tools, agent patterns |
| `r/programming` | General dev tool recommendations |
| `r/devops` | Infrastructure, CI/CD, automation |
| `r/opensource` | OSS project recommendations |
| `r/Python` | Python package ecosystem |
| `r/typescript` | TypeScript tools, libraries |

## Mode B — MCP Server (Full Features)

For richer search with structured output, use `karanb192/reddit-mcp-buddy`:
- 582 GitHub stars, MIT license, actively maintained (pushed 2026-03-17)
- Browse posts, search content, analyze users, read comments

Install:
```bash
npx skills add karanb192/reddit-mcp-buddy -g -a claude-code -y
```

Or add to MCP config:
```json
{
  "mcpServers": {
    "reddit": {
      "command": "npx",
      "args": ["-y", "reddit-mcp-buddy"]
    }
  }
}
```

Requires Reddit API credentials (`REDDIT_CLIENT_ID`, `REDDIT_CLIENT_SECRET`).

## Research Workflow

1. Start with Mode A (public API) — zero friction, sufficient for most research
2. Query: `TOOL_NAME experience` or `TOOL_NAME vs alternatives`
3. Filter by `sort=top&t=year` for quality signal
4. Check 2–3 relevant subreddits from the table above
5. Extract: pain points, alternatives mentioned, version-specific issues, adoption signals

## Example: Research Reddit MCP servers

```bash
# Broad search
curl -s -A "bot/1.0" "https://www.reddit.com/search.json?q=reddit+mcp+server+agent&sort=top&t=year&limit=5" | \
  python3 -c "import json,sys; [print(p['data']['title'], '->', 'https://reddit.com'+p['data']['permalink']) for p in json.load(sys.stdin)['data']['children']]"

# Subreddit-specific
curl -s -A "bot/1.0" "https://www.reddit.com/r/ClaudeAI/search.json?q=mcp+reddit&restrict_sr=on&sort=top&limit=5" | \
  python3 -c "import json,sys; [print(p['data']['title']) for p in json.load(sys.stdin)['data']['children']]"
```

## Common Mistakes

- **Always set `-A` (User-Agent)** — Reddit blocks default `curl/*` user agents with 429
- **Rate limiting** — stay under ~60 req/min on the public API; add `sleep 1` between calls if looping
- **Deleted posts** — body may be `[deleted]`; filter on `score > 5` to reduce noise
- **Old threads** — use `t=year` or `t=month` to avoid stale discussions; AI tooling moves fast
