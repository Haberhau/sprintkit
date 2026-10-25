#!/usr/bin/env python3
"""PreToolUse hook: code edits in a sprintkit project need a ticket in progress.

Reads the hook payload on stdin. Silent outside sprintkit projects and for edits inside
.team/. Otherwise, with no ticket in build (in-progress) or qa (testing):
  "guard": "warn"  (default) tells Claude, the edit goes ahead
  "guard": "block" refuses the edit (exit 2, reason on stderr)
  "guard": "off"   does nothing
"""
import json
import re
import sys
from pathlib import Path

EDITING = {"in-progress", "testing"}  # stages whose executors change code or tests


def project_root(path):
    for d in [path, *path.parents]:
        if (d / ".team" / "config.json").is_file():
            return d
    return None


def main():
    try:
        payload = json.load(sys.stdin)
    except ValueError:
        return 0
    tool_input = payload.get("tool_input") or {}
    raw = tool_input.get("file_path") or tool_input.get("notebook_path")
    if not raw:
        return 0
    target = Path(payload.get("cwd") or ".", raw).resolve()
    root = project_root(target.parent)
    if root is None or (root / ".team") in [target, *target.parents]:
        return 0
    try:
        mode = json.loads((root / ".team/config.json").read_text()).get("guard", "warn")
    except ValueError:
        return 0
    if mode == "off":
        return 0
    for ticket in (root / ".team/tickets").glob("*.md"):
        m = re.search(r"^status:\s*(\S+)", ticket.read_text(errors="replace"), re.M)
        if m and m.group(1) in EDITING:
            return 0
    msg = (f"sprintkit: no ticket is being built or tested, so this edit to {target.relative_to(root)} "
           "happens outside the process. Create a ticket (/sprintkit:ticket) and run its build stage, "
           "or set \"guard\" in .team/config.json.")
    if mode == "block":
        print(msg, file=sys.stderr)
        return 2
    print(json.dumps({"hookSpecificOutput": {"hookEventName": "PreToolUse", "additionalContext": msg}}))
    return 0


if __name__ == "__main__":
    sys.exit(main())
