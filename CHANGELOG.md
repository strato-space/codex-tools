## 2026-04-07

### PROBLEM SOLVED
- Zero-byte Codex session files could effectively disappear from operational lookup even when `session_index.jsonl` still had the thread name, making incident recovery slower and inconsistent.
- Session inspection could not answer which repo/workdir a session belonged to without manual raw-log spelunking.
- Installed skill copies could fail with `Permission denied` when the script entrypoint lost its executable bit.

### FEATURE IMPLEMENTED
- Codex Session Scout now surfaces `cwd` and derived `repo` context directly in `list` output and supports workdir-aware filtering.
- Degraded session recovery now preserves visibility for zero-byte session files and emits a synthetic recovery payload in `fetch`.

### CHANGES
- Added `cwd` / `repo` columns and `--cwd`, `--cwd-regex`, `--repo`, `--repo-regex` filters to `skills/codex-session-scout/scripts/codex-session-scout`.
- Added `session_index.jsonl`-backed recovery metadata for zero-byte and metadata-empty sessions; `fetch --format json` now returns a `session_recovery` payload for degraded cases.
- Tightened recovery after review: full-text queries no longer leak index-only ghost sessions, and readable non-zero session files now keep returning their real event stream even when metadata is sparse.
- Updated `README.md`, `skills/codex-session-scout/SKILL.md`, and `skills/codex-session-scout/agents/openai.yaml` to document cwd/repo-aware lookup and degraded-session recovery.
