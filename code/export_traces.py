"""Stage genuine challenge traces separately from code.zip.

Run once in-session to export completed sessions only. After quitting Codex,
rerun with --after-session-exit to include the now-closed final session, as
required by agent_trace_instructions.md. Original source traces are untouched.
"""
import argparse
from datetime import datetime, timezone
import json
import os
from pathlib import Path
import re
from zipfile import ZipFile, ZIP_DEFLATED


SECRET = re.compile(r"sk-(?:proj-)?[A-Za-z0-9_-]{20,}|AKIA[A-Z0-9]{16}|Bearer\s+[A-Za-z0-9._-]{24,}")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--after-session-exit", action="store_true")
    args = parser.parse_args()
    root = Path(__file__).resolve().parents[1]
    sessions = Path(os.environ.get("CODEX_HOME", str(Path.home() / ".codex"))) / "sessions"
    active = os.environ.get("CODEX_THREAD_ID") or os.environ.get("CODEX_SESSION_ID")
    # An explicit allowlist prevents credential/configuration files from entering.
    paths, pending = [], []
    for path in sorted(sessions.rglob("rollout-*.jsonl")):
        try:
            with path.open(encoding="utf-8") as stream:
                first = json.loads(next(stream))
            meta = first.get("payload", {})
            if first.get("type") != "session_meta" or Path(meta.get("cwd", "/")).resolve() != root:
                continue
        except (OSError, ValueError, StopIteration):
            continue
        if not args.after_session_exit and active and meta.get("id") == active:
            pending.append(str(path))
            continue
        paths.append((path, Path("agent-trace/codex") / path.relative_to(sessions)))
    for events in sorted((root / "runs").rglob("model_events.jsonl")):
        for name in ("model_events.jsonl", "usage.json", "model_prompt.txt", "runtime_stderr.txt"):
            path = events.parent / name
            if path.is_file():
                paths.append((path, Path("agent-trace/application") / path.relative_to(root / "runs")))
    manifest = {"created_at": datetime.now(timezone.utc).isoformat(),
                "complete_after_session_exit": bool(args.after_session_exit),
                "pending_active_sessions": pending,
                "instruction": "Quit Codex, then run python3 code/export_traces.py --after-session-exit and review the ZIP before sharing.",
                "files": [], "redactions": 0}
    target = root / "agent-trace.zip"
    with ZipFile(target, "w", ZIP_DEFLATED) as archive:
        for source, destination in paths:
            original = source.read_text(encoding="utf-8")
            cleaned, count = SECRET.subn("[REDACTED]", original)
            # Substitution never rewrites original trace files or fabricates events.
            archive.writestr(str(destination), cleaned)
            manifest["redactions"] += count
            manifest["files"].append({"source": str(source), "archive_path": str(destination), "redactions": count})
        archive.writestr("agent-trace/export_manifest.json", json.dumps(manifest, indent=2) + "\n")
    (root / "trace_export_manifest.json").write_text(json.dumps(manifest, indent=2) + "\n")
    with ZipFile(target) as archive:
        if archive.testzip():
            raise ValueError("Trace ZIP integrity error")
    print(json.dumps({"path": str(target), "files": len(paths), "redactions": manifest["redactions"],
                      "pending_active_sessions": pending, "complete": manifest["complete_after_session_exit"]}, indent=2))


if __name__ == "__main__":
    main()
