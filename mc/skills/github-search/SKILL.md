---
name: github-search
description: Use when researching GitHub repositories, evaluating open-source tools, discovering agent skills or MCP servers, scoring repo health, or searching by topic/keyword/language using only the public GitHub REST API.
---

# GitHub Search

Search and evaluate public GitHub repositories using the GitHub REST API — no MCP server, no authentication required for basic usage.

## API Base

```
https://api.github.com
```

Rate limits: 60 req/hour (unauthenticated), 5,000/hour with `GITHUB_TOKEN`.

## Core Operations

### Search repositories

```bash
curl -s "https://api.github.com/search/repositories?q=QUERY&sort=stars&order=desc&per_page=10"
```

Query syntax:
- Keyword: `mcp+server+github`
- Topic filter: `topic:agent-skill`
- Language filter: `language:typescript`
- Star filter: `stars:>500`
- Combined: `reddit+mcp+server+language:typescript+stars:>100`

### Get repo metadata

```bash
curl -s "https://api.github.com/repos/{owner}/{repo}"
```

Key fields: `stargazers_count`, `pushed_at`, `license.spdx_id`, `description`, `topics`, `open_issues_count`, `forks_count`, `archived`.

### Extract summary (one-liner)

```bash
curl -s "https://api.github.com/repos/{owner}/{repo}" | python3 -c "
import json,sys; d=json.load(sys.stdin)
print(f'Stars: {d[\"stargazers_count\"]} | Last push: {d[\"pushed_at\"][:10]} | License: {d.get(\"license\") and d[\"license\"][\"spdx_id\"]} | Archived: {d[\"archived\"]}')
"
```

### Search topics

```bash
curl -s "https://api.github.com/search/topics?q=agent-skill" \
  -H "Accept: application/vnd.github.mercy-preview+json"
```

### List contents of a directory

```bash
curl -s "https://api.github.com/repos/{owner}/{repo}/contents/{path}"
```

### Read a raw file

```bash
curl -s "https://raw.githubusercontent.com/{owner}/{repo}/refs/heads/main/{path}"
```

## Repo Health Scoring Rubric

Use when evaluating a repo for adoption. Score each dimension:

| Dimension | Signal | Score |
|---|---|---|
| Stars | >10k=30, >1k=20, >100=10, <100=5 | 0–30 |
| Last push | <30d=25, <90d=20, <180d=15, <365d=10, >365d=0 | 0–25 |
| License | MIT/Apache-2.0=10, BSD=8, GPL=5, unknown=0 | 0–10 |
| Archived | false=10, true=0 | 0–10 |
| Open issues | <50=5, <200=3, >200=0 | 0–5 |

Total: 0–80. Recommend ≥50 for adoption.

## Workflow for S&K Research

1. Search by keyword + relevant filters
2. Collect top 5–10 results
3. For each: fetch metadata, compute health score
4. Filter out archived repos and unknown licenses
5. Rank by composite score
6. Read SKILL.md or README for the top 2–3 candidates

## Example: Find Reddit MCP servers

```bash
curl -s "https://api.github.com/search/repositories?q=reddit+mcp+server&sort=stars&order=desc&per_page=8" | python3 -c "
import json,sys
d=json.load(sys.stdin)
for r in d.get('items', []):
    lic = r['license']['spdx_id'] if r.get('license') else 'none'
    print(f\"{r['full_name']} | ★{r['stargazers_count']} | {lic} | pushed:{r['pushed_at'][:10]} | {(r['description'] or '')[:60]}\")
"
```

## Common Mistakes

- **Don't use GraphQL** for simple lookups — REST is sufficient and requires no token
- **Don't skip license check** — unknown/proprietary licenses block adoption
- **Archived repos** still appear in search — always filter `archived: false`
- **Stars ≠ quality** — check `pushed_at` to confirm active maintenance
