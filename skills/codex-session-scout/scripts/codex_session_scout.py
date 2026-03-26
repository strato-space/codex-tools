#!/usr/bin/env python3
"""Inspect local Codex session history, live activity, and event streams."""
import argparse
import gzip
import json
import os
import re
import subprocess
import sys
from contextlib import contextmanager
from datetime import datetime, timezone
from pathlib import Path

__version__ = "1.0.0"

DEFAULT_SESSIONS_DIR = "/root/.codex/sessions"
DEFAULT_ARCHIVED_DIR = "/root/.codex/archived_sessions"
SESSION_INDEX_FILE = "session_index.jsonl"

UUID_RE = re.compile(
    r"[0-9a-fA-F]{8}-"
    r"[0-9a-fA-F]{4}-"
    r"[0-9a-fA-F]{4}-"
    r"[0-9a-fA-F]{4}-"
    r"[0-9a-fA-F]{12}"
)


@contextmanager
def open_session_text(path: Path):
    """
    Open a Codex session file as a text stream.

    Supports:
    - *.jsonl
    - *.jsonl.gz
    - *.jsonl.zst (via external `zstd -dc`)
    """

    name = path.name
    if name.endswith(".jsonl.gz"):
        f = gzip.open(path, "rt", encoding="utf-8", errors="replace")
        try:
            yield f
        finally:
            f.close()
        return

    if name.endswith(".jsonl.zst"):
        proc = subprocess.Popen(
            ["zstd", "-dc", str(path)],
            stdout=subprocess.PIPE,
            stderr=subprocess.DEVNULL,
            text=True,
            encoding="utf-8",
            errors="replace",
        )
        try:
            assert proc.stdout is not None
            yield proc.stdout
        finally:
            try:
                if proc.stdout:
                    proc.stdout.close()
            finally:
                # Closing stdout typically terminates zstd with EPIPE; either way, ensure it exits.
                try:
                    proc.terminate()
                except Exception:
                    pass
                try:
                    proc.wait(timeout=1)
                except Exception:
                    pass
        return

    with path.open("r", encoding="utf-8", errors="replace") as f:
        yield f


def tail_session_event(path: Path) -> tuple[datetime | None, bool]:
    """
    Read the last JSONL event cheaply for live-activity checks.

    For compressed files we fall back to mtime elsewhere; active sessions are plain
    JSONL in the live sessions dir, so optimize for that case.
    """

    if not path.name.endswith(".jsonl"):
        return None, False

    try:
        with path.open("rb") as f:
            f.seek(0, os.SEEK_END)
            end = f.tell()
            if end <= 0:
                return None, False

            pos = end - 1
            while pos >= 0:
                f.seek(pos)
                if f.read(1) not in {b"\n", b"\r"}:
                    break
                pos -= 1

            if pos < 0:
                return None, False

            start = pos
            while start >= 0:
                f.seek(start)
                if f.read(1) == b"\n":
                    start += 1
                    break
                start -= 1

            if start < 0:
                start = 0

            f.seek(start)
            raw = f.read(pos - start + 1)
    except OSError:
        return None, False

    try:
        obj = json.loads(raw.decode("utf-8", errors="replace").strip())
    except Exception:
        return None, False

    payload = obj.get("payload") or {}
    last_ts = parse_iso(obj.get("timestamp") or "")
    completed = obj.get("type") == "event_msg" and payload.get("type") == "task_complete"
    return last_ts, completed


def parse_iso(ts: str) -> datetime | None:
    if not ts:
        return None
    try:
        return datetime.fromisoformat(ts.replace("Z", "+00:00"))
    except Exception:
        return None


def extract_id_from_filename(name: str) -> str:
    match = UUID_RE.search(name)
    if not match:
        return ""
    return match.group(0)


def extract_title_from_message(message: str) -> str:
    lines = [line.strip() for line in message.splitlines()]
    for i, line in enumerate(lines):
        if "My request for Codex" in line:
            for j in range(i + 1, len(lines)):
                if lines[j]:
                    return lines[j]
            return ""
    for line in lines:
        if not line:
            continue
        if line.startswith("#"):
            continue
        return line
    return ""


def load_thread_names(dirs: list[str]) -> dict[str, str]:
    names: dict[str, str] = {}
    codex_homes = {str(Path(d).resolve().parent) for d in dirs}
    for codex_home in codex_homes:
        index_path = Path(codex_home) / SESSION_INDEX_FILE
        if not index_path.exists():
            continue
        try:
            with index_path.open("r", encoding="utf-8", errors="replace") as f:
                for line in f:
                    try:
                        obj = json.loads(line)
                    except Exception:
                        continue
                    thread_id = str(obj.get("id") or "").strip()
                    thread_name = str(obj.get("thread_name") or "").strip()
                    if thread_id and thread_name:
                        names[thread_id] = thread_name
        except OSError:
            continue
    return names


def session_info(path: Path, thread_names: dict[str, str] | None = None) -> dict:
    ts = None
    session_id = ""
    preview = ""
    try:
        with open_session_text(path) as f:
            for line in f:
                try:
                    obj = json.loads(line)
                except Exception:
                    continue
                if obj.get("type") == "session_meta":
                    payload = obj.get("payload") or {}
                    if not session_id:
                        session_id = (
                            payload.get("id")
                            or payload.get("session_id")
                            or payload.get("sessionId")
                            or ""
                        )
                    if not ts:
                        ts_val = payload.get("timestamp") or obj.get("timestamp")
                        parsed = parse_iso(ts_val)
                        if parsed:
                            ts = parsed
                elif obj.get("type") == "event_msg":
                    payload = obj.get("payload") or {}
                    if payload.get("type") == "user_message":
                        if not preview:
                            msg = payload.get("message") or ""
                            preview = extract_title_from_message(msg)
                if ts and session_id and preview:
                    break
    except Exception:
        pass
    live_ts = datetime.fromtimestamp(path.stat().st_mtime, tz=timezone.utc)
    if not ts:
        ts = live_ts
    if not session_id:
        session_id = extract_id_from_filename(path.name)
    thread_name = (thread_names or {}).get(session_id, "")
    title = thread_name or preview
    return {
        "path": path,
        "ts": ts,
        "last_ts": live_ts,
        "title": title,
        "preview": preview,
        "thread_name": thread_name,
        "id": session_id,
        "completed": False,
    }


def age_string(ts: datetime, now: datetime) -> str:
    delta = now - ts
    seconds = int(delta.total_seconds())
    if seconds < 0:
        seconds = 0
    if seconds < 60:
        return f"{seconds}s"
    if seconds < 3600:
        return f"{max(1, seconds // 60)}m"
    if seconds < 86400:
        return f"{seconds // 3600}h"
    return f"{seconds // 86400}d"


def session_status(item: dict, now: datetime, active_window_seconds: int) -> str:
    if item.get("completed"):
        return "completed"
    live_ts = item.get("last_ts") or item["ts"]
    if (now - live_ts).total_seconds() <= active_window_seconds:
        return "running"
    return "stale"


def truncate(text: str, max_len: int) -> str:
    if max_len <= 0:
        return text
    if len(text) <= max_len:
        return text
    return text[: max_len - 1].rstrip() + "…"


def iter_session_paths(dirs: list[str]):
    for d in dirs:
        root = Path(d)
        if not root.exists():
            continue
        patterns = ("*.jsonl", "*.jsonl.gz", "*.jsonl.zst")
        for pattern in patterns:
            for path in root.rglob(pattern):
                if path.is_file():
                    yield path


def collect_sessions(
    dirs: list[str],
    include_empty: bool,
    name_query: str | None,
    match_patterns: list[re.Pattern[str]] | None = None,
) -> list[dict]:
    items = []
    thread_names = load_thread_names(dirs)
    query_norm = name_query.casefold() if name_query else None
    for path in iter_session_paths(dirs):
        info = session_info(path, thread_names=thread_names)
        title = info["title"]
        preview = info.get("preview") or ""
        thread_name = info.get("thread_name") or ""
        session_id = info["id"] or ""
        if not include_empty and not title:
            continue
        if query_norm:
            haystacks = (title, preview, thread_name, session_id)
            if not any(h and query_norm in h.casefold() for h in haystacks):
                continue
        if match_patterns:
            haystacks = (title, preview, thread_name, session_id)
            if not any(
                h and any(pattern.search(h) for pattern in match_patterns)
                for h in haystacks
            ):
                continue
        items.append(info)
    items.sort(key=lambda x: x["ts"], reverse=True)
    return items


def build_search_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Inspect local Codex sessions by title or id."
    )
    parser.add_argument(
        "--version",
        action="store_true",
        help="Show script version and exit.",
    )
    parser.add_argument(
        "--limit",
        type=int,
        default=10000,
        help="Number of sessions to show (capped at 10000).",
    )
    parser.add_argument(
        "--include-archived",
        action="store_true",
        help="Include archived sessions.",
    )
    parser.add_argument(
        "--max-len",
        type=int,
        default=80,
        help="Max title length before truncation (0 to disable).",
    )
    parser.add_argument(
        "--include-empty",
        action="store_true",
        help="Include sessions without a detected title.",
    )
    parser.add_argument(
        "--search",
        help="Case-insensitive substring filter for the session title or id.",
    )
    parser.add_argument(
        "--match",
        action="append",
        default=[],
        metavar="REGEX",
        help=(
            "Case-insensitive regex filter, matched like grep against the "
            "session title and id. May be passed multiple times."
        ),
    )
    parser.add_argument(
        "--show-age",
        action="store_true",
        help="Include age column.",
    )
    parser.add_argument(
        "--show-live-age",
        action="store_true",
        help=(
            "Include age since the last observed event and sort active-now "
            "sessions to the top."
        ),
    )
    parser.add_argument(
        "--active-now-minutes",
        type=int,
        default=5,
        help=(
            "Window in minutes used by --show-live-age to decide whether a "
            "session is active right now (default: 5)."
        ),
    )
    parser.add_argument(
        "--show-status",
        action="store_true",
        help=(
            "Include a derived status column: running, completed, or stale."
        ),
    )
    parser.add_argument(
        "--live-within-minutes",
        type=int,
        help=(
            "Only show sessions whose live activity was within the last N "
            "minutes. Also sorts by live recency."
        ),
    )
    parser.add_argument(
        "--live-last-day",
        "--live-24h",
        "--today",
        dest="live_last_day",
        action="store_true",
        help=(
            "Alias for --live-within-minutes 1440. Shows only sessions with "
            "live activity in the last 24 hours."
        ),
    )
    parser.add_argument(
        "--show-id",
        dest="show_id",
        action="store_true",
        help="Include session id column.",
    )
    parser.add_argument(
        "--hide-id",
        dest="show_id",
        action="store_false",
        help="Hide session id column.",
    )
    parser.add_argument(
        "--show-path",
        dest="show_path",
        action="store_true",
        help="Include path column.",
    )
    parser.add_argument(
        "--hide-path",
        dest="show_path",
        action="store_false",
        help="Hide path column.",
    )
    parser.add_argument(
        "--tsv",
        action="store_true",
        help="Output as tab-separated values.",
    )
    parser.add_argument(
        "--path-style",
        choices=["full", "name"],
        default="full",
        help="Show full path or just the filename.",
    )
    parser.add_argument(
        "--show-file",
        action="store_true",
        help="Alias for --path-style name.",
    )
    parser.add_argument(
        "--ops",
        action="store_true",
        help=(
            "Operational view: show live age first, then age and status, "
            "with compact output. Useful with --today."
        ),
    )
    parser.add_argument(
        "patterns",
        nargs="*",
        help=(
            "Optional grep-like regex patterns matched case-insensitively "
            "against the session title and id."
        ),
    )
    parser.set_defaults(show_id=False, show_path=False)
    return parser


def build_fetch_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Fetch a Codex session by id."
    )
    parser.add_argument(
        "session_id",
        nargs="?",
        help="Session id to fetch.",
    )
    parser.add_argument(
        "--version",
        action="store_true",
        help="Show script version and exit.",
    )
    parser.add_argument(
        "--include-archived",
        action="store_true",
        help="Include archived sessions.",
    )
    parser.add_argument(
        "--format",
        choices=["jsonl", "json"],
        default="jsonl",
        help="Output format for fetched content.",
    )
    return parser


def parse_args():
    argv = sys.argv[1:]
    search_parser = build_search_parser()
    fetch_parser = build_fetch_parser()
    if argv and argv[0] in {"search", "fetch"}:
        command = argv[0]
        rest = argv[1:]
    else:
        command = "search"
        rest = argv
    parser = fetch_parser if command == "fetch" else search_parser
    args = parser.parse_args(rest)
    args.command = command
    return args


def find_session_by_id(dirs: list[str], session_id: str) -> Path | None:
    if not session_id:
        return None
    for path in iter_session_paths(dirs):
        if extract_id_from_filename(path.name) == session_id:
            return path
    for path in iter_session_paths(dirs):
        info = session_info(path)
        if info.get("id") == session_id:
            return path
    return None


def fetch_session(path: Path, output_format: str) -> int:
    if output_format == "jsonl":
        with open_session_text(path) as f:
            for line in f:
                print(line.rstrip("\n"))
        return 0
    payload: list[object] = []
    with open_session_text(path) as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            try:
                payload.append(json.loads(line))
            except Exception:
                payload.append({"_raw": line})
    print(json.dumps(payload, ensure_ascii=False, indent=2))
    return 0


def exit_for_broken_stdout_pipe() -> int:
    # Point stdout at /dev/null so interpreter shutdown does not raise again.
    try:
        devnull_fd = os.open(os.devnull, os.O_WRONLY)
    except OSError:
        return 0
    try:
        os.dup2(devnull_fd, sys.stdout.fileno())
    except OSError:
        pass
    finally:
        os.close(devnull_fd)
    return 0


def run_search(args: argparse.Namespace) -> int:
    if args.version:
        print(__version__)
        return 0

    dirs = [DEFAULT_SESSIONS_DIR]
    if args.include_archived:
        dirs.append(DEFAULT_ARCHIVED_DIR)

    now = datetime.now(timezone.utc)
    limit = min(max(0, args.limit), 10000)
    match_patterns: list[re.Pattern[str]] = []
    live_within_minutes = args.live_within_minutes
    if args.live_last_day and live_within_minutes is None:
        live_within_minutes = 24 * 60
    show_status = args.show_status or args.ops
    show_age = args.show_age or args.ops
    show_live_age = args.show_live_age or args.ops
    for raw_pattern in [*args.match, *args.patterns]:
        try:
            match_patterns.append(re.compile(raw_pattern, re.IGNORECASE))
        except re.error as exc:
            print(f"Invalid regex pattern {raw_pattern!r}: {exc}", file=sys.stderr)
            return 2
    sessions = collect_sessions(
        dirs,
        args.include_empty,
        args.search,
        match_patterns=match_patterns,
    )
    if live_within_minutes is not None:
        live_window_seconds = max(0, live_within_minutes) * 60
        sessions = [
            item
            for item in sessions
            if (now - (item.get("last_ts") or item["ts"])).total_seconds()
            <= live_window_seconds
        ]
    if show_live_age or show_status or live_within_minutes is not None:
        active_window_seconds = max(0, args.active_now_minutes) * 60
        for item in sessions:
            live_ts = item.get("last_ts") or item["ts"]
            if not show_status and (now - live_ts).total_seconds() > active_window_seconds:
                continue
            _, item["completed"] = tail_session_event(item["path"])

        def is_active_now(item: dict) -> bool:
            return session_status(item, now, active_window_seconds) == "running"

        sessions.sort(
            key=lambda item: (
                0 if is_active_now(item) else 1,
                -((item.get("last_ts") or item["ts"]).timestamp()),
                -(item["ts"].timestamp()),
            )
        )
    sessions = sessions[:limit]

    for item in sessions:
        title = item["title"] or "(untitled session)"
        title = truncate(title, args.max_len)
        session_id = item["id"] or "-"
        age = age_string(item["ts"], now)
        live_ts = item.get("last_ts") or item["ts"]
        live_age = age_string(live_ts, now)
        path_style = "name" if args.show_file else args.path_style
        path_value = item["path"].name if path_style == "name" else str(item["path"])
        extras = []
        status = session_status(item, now, max(0, args.active_now_minutes) * 60)
        active_now = status == "running"
        live_label = live_age if (args.ops or show_status) else f"{live_age}{'*' if active_now else ''}"
        if args.ops and show_live_age:
            extras.append(live_label if args.tsv else f"{live_label:>3}")
        if show_age:
            extras.append(age if args.tsv else f"{age:>3}")
        if show_status:
            extras.append(status if args.tsv else f"{status:>9}")
        if show_live_age and not args.ops:
            extras.append(live_label if args.tsv else f"{live_label:>3}")
        if args.show_id:
            extras.append(session_id)
        if args.show_path:
            extras.append(path_value)
        columns = [*extras, title] if extras else [title]
        if args.tsv:
            print("\t".join(columns))
        else:
            print("  ".join(columns))
    return 0


def run_fetch(args: argparse.Namespace) -> int:
    if args.version:
        print(__version__)
        return 0
    if not args.session_id:
        print("Session id is required for fetch.", file=sys.stderr)
        return 2
    dirs = [DEFAULT_SESSIONS_DIR]
    if args.include_archived:
        dirs.append(DEFAULT_ARCHIVED_DIR)
    path = find_session_by_id(dirs, args.session_id)
    if not path:
        print(f"Session id not found: {args.session_id}", file=sys.stderr)
        return 1
    return fetch_session(path, args.format)


def main() -> int:
    args = parse_args()
    try:
        if args.command == "fetch":
            return run_fetch(args)
        return run_search(args)
    except BrokenPipeError:
        return exit_for_broken_stdout_pipe()


if __name__ == "__main__":
    raise SystemExit(main())
