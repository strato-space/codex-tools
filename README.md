# Codex Session Scout

Codex Session Scout is a compact inspection tool for local Codex session logs.

It is built for the moments when the normal picker is too slow or too visual: finding the sessions that are active right now, sorting by fresh live activity, locating a thread by partial title or session id, and tailing the raw event stream when you need to understand what a session is actually doing.

## What It Does

- Lists local Codex sessions from `~/.codex/sessions`
- Optionally includes archived sessions from `~/.codex/archived_sessions`
- Reads renamed thread names from `session_index.jsonl`
- Sorts active sessions to the top using recent file activity
- Shows compact operational views with `live age`, `age`, and derived `status`
- Filters by substring or grep-style regex against thread name, preview, or session id
- Fetches the full JSONL or JSON payload for any session id

## Quick Start

```bash
uv run codex_session_scout.py --today --ops --show-id
```

Example output:

```text
 0s  12m    running  019d1234-aaaa-bbbb-cccc-1234567890ab  Release lane follow-up
 3m  28m  completed  019d1234-aaaa-bbbb-cccc-1234567890ac  Docs polish
14m   2h      stale  019d1234-aaaa-bbbb-cccc-1234567890ad  Regression sweep
```

## Useful Commands

Show the operational view for sessions with live activity in the last 24 hours:

```bash
uv run codex_session_scout.py --today --ops
```

Filter by partial thread name or id:

```bash
uv run codex_session_scout.py --today --ops worker
uv run codex_session_scout.py --show-id 019d1234
```

Use regex matching like `grep`:

```bash
uv run codex_session_scout.py --match 'review|postreview' --show-id
```

Inspect the raw event stream for one session:

```bash
uv run codex_session_scout.py fetch 019d1234-aaaa-bbbb-cccc-1234567890ab
```

Fetch as pretty JSON:

```bash
uv run codex_session_scout.py fetch --format json 019d1234-aaaa-bbbb-cccc-1234567890ab
```

## Status Model

- `running`: recent live activity and the latest event is not `task_complete`
- `completed`: the latest event is `task_complete`
- `stale`: not completed, but no longer active in the current live window

`--today` is an alias for "live activity within the last 24 hours". It is not a calendar-day filter.

## Skill

This repository includes an installable Codex skill at:

`skills/codex-session-scout`

After installing the skill, Codex can use the tool to:

- find active sessions
- locate a session by title fragment or id
- inspect recent activity
- fetch a session and summarize the latest messages

## Files

- [`codex_session_scout.py`](./codex_session_scout.py): root launcher
- [`skills/codex-session-scout/scripts/codex_session_scout.py`](./skills/codex-session-scout/scripts/codex_session_scout.py): core implementation
- [`skills/codex-session-scout/SKILL.md`](./skills/codex-session-scout/SKILL.md): reusable skill definition

## License

MIT
