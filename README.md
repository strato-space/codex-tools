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

## CLI Design

The command-line interface was redesigned as an explicit subcommand CLI.

- No implicit default command
- No positional grep shortcuts
- No alias flags for the same concept
- One filtering model for text, regex, status, and live-activity windows
- One output model based on `--view` presets or explicit `--columns`

The public executable uses `dash-case`: `codex-session-scout`.

That choice is deliberate. This project exposes a shell command, not a Python import API, and dash-case is easier to scan in shell history, docs, and pasted commands. Underscores remain fine for internal Python modules, but not as the primary CLI surface.

## Quick Start

```bash
uv run ./codex-session-scout list --view ops --active-within 24h
```

Example output:

```text
 0s  12m  running    019d1234-aaaa-bbbb-cccc-1234567890ab  Release lane follow-up
 3m  28m  completed  019d1234-aaaa-bbbb-cccc-1234567890ac  Docs polish
14m   2h  stale      019d1234-aaaa-bbbb-cccc-1234567890ad  Regression sweep
```

## Useful Commands

Show the operational view for sessions with live activity in the last 24 hours:

```bash
uv run ./codex-session-scout list --view ops --active-within 24h
```

Filter by partial thread name or id:

```bash
uv run ./codex-session-scout list --query worker --view ops
uv run ./codex-session-scout list --query 019d1234 --columns id,title
```

Use regex matching like `grep`:

```bash
uv run ./codex-session-scout list --regex 'review|postreview' --view ops
```

Inspect the raw event stream for one session:

```bash
uv run ./codex-session-scout fetch 019d1234-aaaa-bbbb-cccc-1234567890ab
```

Fetch as pretty JSON:

```bash
uv run ./codex-session-scout fetch --format json 019d1234-aaaa-bbbb-cccc-1234567890ab
```

Build a custom table shape:

```bash
uv run ./codex-session-scout list --columns live,age,status,id,title --format table
```

Emit structured JSON for automation:

```bash
uv run ./codex-session-scout list --source all --status running --format json
```

## Status Model

- `running`: recent live activity and the latest event is not `task_complete`
- `completed`: the latest event is `task_complete`
- `stale`: not completed, but no longer active in the current live window

Use `--running-window 5m` to control when a session is considered live. Use `--active-within 24h` when you want a filter, not a status threshold.

## Skill

This repository includes an installable Codex skill at:

`skills/codex-session-scout`

After installing the skill, Codex can use the tool to:

- find active sessions
- locate a session by title fragment or id
- inspect recent activity
- fetch a session and summarize the latest messages

## Files

- [`codex-session-scout`](./codex-session-scout): root launcher
- [`skills/codex-session-scout/scripts/codex-session-scout`](./skills/codex-session-scout/scripts/codex-session-scout): core implementation
- [`skills/codex-session-scout/SKILL.md`](./skills/codex-session-scout/SKILL.md): reusable skill definition

## License

MIT
