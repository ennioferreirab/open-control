# Story 1.6a: Default Mission Control Startup To Local Convex

Status: ready

## Story

As a developer,
I want `nanobot mc start` to use a local Convex deployment by default and expose Cloud as an explicit override,
So that development traffic does not consume Convex Cloud function quotas.

## Acceptance Criteria

1. Given the user runs `uv run nanobot mc start`, when Mission Control starts, then the Convex subprocess uses local mode.
2. Given the user runs `uv run nanobot mc start --cloud`, when Mission Control starts, then the Convex subprocess uses Cloud mode.
3. Given the user runs `uv run nanobot mc start --local`, when Mission Control starts, then the Convex subprocess uses local mode explicitly.
4. Given the user passes both `--local` and `--cloud`, when the CLI validates arguments, then it exits with a clear error.

## Tasks

- [ ] Add CLI flags for Convex startup mode selection on `mc start`
- [ ] Default startup to local Convex mode
- [ ] Keep Cloud mode available via `--cloud`
- [ ] Add regression tests for process configuration and CLI validation
