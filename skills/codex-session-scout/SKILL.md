---
name: codex-session-scout
description: Inspect local Codex session logs, find active threads, filter by title or session id, and fetch recent event streams. Use when you need to understand what Codex sessions are doing right now or to recover the status of a specific thread.
---

# Codex Session Scout

Use this skill when the task is about local Codex session history or live thread activity.

Typical uses:

- find the sessions that are active right now
- locate a session by partial title or session id
- check whether a session is `running`, `completed`, or `stale`
- fetch a session and inspect the latest messages or raw events

## Commands

Run the bundled tool directly:

```bash
uv run ~/.agents/skills/codex-session-scout/scripts/codex-session-scout list --view ops --active-within 24h
```

Filter by a title fragment or id:

```bash
uv run ~/.agents/skills/codex-session-scout/scripts/codex-session-scout list --query build --view ops
```

Use regex matching:

```bash
uv run ~/.agents/skills/codex-session-scout/scripts/codex-session-scout list --regex 'review|worker' --view ops
```

Fetch one session:

```bash
uv run ~/.agents/skills/codex-session-scout/scripts/codex-session-scout fetch <session-id>
```

## Workflow

1. Start with `list --view ops --active-within 24h` when the user wants a live operational view.
2. Add `--query` or `--regex` when the session list is noisy.
3. Use `fetch <session-id>` when the user asks what a session is doing or what it did last.
4. Summarize the relevant recent events instead of dumping the entire log unless the user asks for raw output.

## Notes

- The public CLI uses dash-case command names and explicit subcommands.
- The tool reads renamed thread names from `session_index.jsonl` when available.
- The default data sources are `/root/.codex/sessions` and `/root/.codex/archived_sessions`.
