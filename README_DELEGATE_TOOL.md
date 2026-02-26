# Mission Control Delegation Tool
This branch introduces a new feature that allows the native Nanobot (e.g. from Telegram or CLI) to delegate tasks directly to the Mission Control dashboard. 
It uses the native `HEARTBEAT.md` mechanism to notify the user asynchronously when the assigned agent finishes the job.

1. Switched polling in `McDelegateTool` to `HEARTBEAT.md` notifications.
2. Updated `executor.py` to write completion logs directly to `HEARTBEAT.md`.
3. Adjusted the `interval_s` of `HeartbeatService` in the CLI from 30 minutes to 2 minutes for faster updates.
