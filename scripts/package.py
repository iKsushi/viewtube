#!/usr/bin/env python3
"""Package tracked source, full Git history and original project-native sessions."""

import argparse
import hashlib
import json
import subprocess
import zipfile
from datetime import UTC, datetime
from pathlib import Path


def git(root, *args):
    return subprocess.check_output(["git", "-C", str(root), *args])


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--session", type=Path, action="append", required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument(
        "--allow-session-id",
        action="append",
        default=[],
        help="Explicitly approve an additional project session UUID",
    )
    args = parser.parse_args()
    root = Path(__file__).resolve().parents[1]
    if git(root, "status", "--porcelain").strip():
        raise SystemExit(
            "Commit project changes before packaging (history must match delivered source)."
        )
    # Read complete native files once. Never redact, synthesize or rewrite messages.
    sessions = []
    for path in args.session:
        data = path.read_bytes()
        records = [json.loads(line) for line in data.splitlines() if line.strip()]
        metadata = next(
            (v.get("payload", {}) for v in records if v.get("type") == "session_meta"),
            None,
        )
        if not metadata or metadata.get("id") not in {
            "01a1a14d-e714-77a0-85f2-afc12f7816ea",
            *args.allow_session_id,
        }:
            raise SystemExit("Refusing a session unrelated to this project")
        if any(sid == metadata["id"] or name == path.name for name, _, sid in sessions):
            raise SystemExit("Duplicate session ID or filename")
        sessions.append((path.name, data, metadata["id"]))
    manifest = {
        "captured_at_utc": datetime.now(UTC).isoformat(),
        "git_head": git(root, "rev-parse", "HEAD").decode().strip(),
        "format": "Original Codex JSONL, exact bytes at capture time",
        "note": "The active session may continue after this snapshot; re-run packaging for a later capture.",
        "sessions": [
            {
                "file": name,
                "session_id": sid,
                "bytes": len(data),
                "sha256": hashlib.sha256(data).hexdigest(),
            }
            for name, data, sid in sessions
        ],
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(args.output, "w", zipfile.ZIP_DEFLATED) as archive:
        files = [
            root / p.decode() for p in git(root, "ls-files", "-z").split(b"\0") if p
        ]
        files += [p for p in (root / ".git").rglob("*") if p.is_file()]
        for path in files:
            if path.is_symlink():
                raise SystemExit(f"Refusing symlink in submission: {path.name}")
            archive.write(path, "viewtube/" + path.relative_to(root).as_posix())
        for name, data, _ in sessions:
            archive.writestr("viewtube/ai/sessions/" + name, data)
        archive.writestr(
            "viewtube/ai/sessions/manifest.json",
            json.dumps(manifest, ensure_ascii=False, indent=2),
        )
    with zipfile.ZipFile(args.output) as archive:
        if archive.testzip():
            raise SystemExit("ZIP verification failed")
    digest = hashlib.sha256(args.output.read_bytes()).hexdigest()
    args.output.with_suffix(".zip.sha256").write_text(f"{digest}  {args.output.name}\n")
    print(
        f"Created {args.output.name}: {args.output.stat().st_size} bytes, HEAD {manifest['git_head'][:8]}"
    )


if __name__ == "__main__":
    main()
