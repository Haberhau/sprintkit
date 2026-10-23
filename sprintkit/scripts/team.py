#!/usr/bin/env python3
"""sprintkit runner: all bookkeeping, zero tokens. See docs/stage-contract.md.

  team.py init [--prefix PROJ]
  team.py new <story|bug|chore|spike> "<title>"
  team.py board
  team.py start <stage> <ID>     # precondition, status, branch, context, executor
  team.py finish <stage> <ID>    # gates, advance or bounce
"""
import json
import os
import re
import subprocess
import sys
from datetime import datetime
from pathlib import Path

TEAM = Path(".team")
TICKETS = TEAM / "tickets"
CONFIG = TEAM / "config.json"

# stage -> (status while running, status on pass, status on fail)
STAGES = {
    "refine": ("refining", "refined", "backlog"),
    "build": ("in-progress", "in-review", "in-progress"),
}
DEFAULT_FLOWS = {
    "story": ["refine", "build", "review", "qa"],
    "bug": ["build", "qa"],
    "chore": ["build"],
    "spike": ["refine", "build"],
}
DEFAULT_CONFIG = {
    "prefix": "PROJ",
    "base_branch": "main",
    "stages": {
        "refine": {"agent": "sprintkit:tech-lead"},
        "build": {"agent": "sprintkit:developer"},
    },
    "context": [],
    "context_by_stage": {},
    "context_max_chars": 4000,
    "gates": {},
    "gate_default_mode": "warn",
    "flows": DEFAULT_FLOWS,
}
BOARD_COLUMNS = ["backlog", "refining", "refined", "in-progress", "in-review",
                 "in-qa", "done", "release-candidate", "released"]

TEMPLATE = """---
id: {id}
type: {type}
title: {title}
status: backlog
blocked: false
---

## Description

## Acceptance criteria

## Technical notes

## Implementation notes

## Review notes

## QA notes

## Log
"""


def die(msg):
    sys.exit(f"error: {msg}")


def load_config():
    if not CONFIG.exists():
        die("no .team/config.json, run `init` first")
    cfg = {**DEFAULT_CONFIG, **json.loads(CONFIG.read_text())}
    cfg["stages"] = {**DEFAULT_CONFIG["stages"], **cfg.get("stages", {})}
    cfg["flows"] = {**DEFAULT_FLOWS, **cfg.get("flows", {})}
    return cfg


# ---------- ticket file ----------

def parse(path):
    text = path.read_text()
    m = re.match(r"---\n(.*?)\n---\n(.*)", text, re.S)
    if not m:
        die(f"{path}: missing frontmatter")
    meta = {}
    for line in m.group(1).splitlines():
        k, _, v = line.partition(":")
        meta[k.strip()] = v.strip()
    return meta, m.group(2)


def write(path, meta, body):
    head = "\n".join(f"{k}: {v}" for k, v in meta.items())
    path.write_text(f"---\n{head}\n---\n{body}")


def find(ticket_id):
    hits = list(TICKETS.glob(f"{ticket_id}-*.md"))
    if not hits:
        die(f"ticket {ticket_id} not found")
    return hits[0]


def section(body, name):
    m = re.search(rf"^## {re.escape(name)}\n(.*?)(?=^## |\Z)", body, re.S | re.M)
    return m.group(1).strip() if m else ""


def log(meta, body, msg):
    stamp = datetime.now().strftime("%Y-%m-%dT%H:%M")
    return body.rstrip("\n") + f"\n- {stamp} {msg}\n"


def ticket_env(meta, path):
    # Ticket data reaches commands only via env vars, never interpolated into the string.
    return {**os.environ,
            "TICKET_ID": meta["id"], "TICKET_TITLE": meta["title"],
            "TICKET_TYPE": meta["type"], "TICKET_PATH": str(path),
            "TICKET_BRANCH": meta.get("branch", "")}


def sh(cmd, env=None):
    return subprocess.run(cmd, shell=True, env=env, capture_output=True, text=True)


def git(*args):
    r = subprocess.run(["git", *args], capture_output=True, text=True)
    if r.returncode:
        die(f"git {' '.join(args)}: {r.stderr.strip()}")
    return r.stdout.strip()


# ---------- commands ----------

def cmd_init(args):
    prefix = args[args.index("--prefix") + 1] if "--prefix" in args else "PROJ"
    TICKETS.mkdir(parents=True, exist_ok=True)
    if CONFIG.exists():
        print(f"{CONFIG} already exists, left untouched")
        return
    base = sh("git symbolic-ref --short HEAD").stdout.strip() or "main"
    cfg = {"prefix": prefix, "base_branch": base,
           "stages": DEFAULT_CONFIG["stages"],
           "context": [], "gates": {}, "gate_default_mode": "warn"}
    CONFIG.write_text(json.dumps(cfg, indent=2) + "\n")
    print(f"created {CONFIG} (prefix {prefix}, base branch {base})")


def cmd_new(args):
    if len(args) != 2 or args[0] not in DEFAULT_FLOWS:
        die(f"usage: new <{'|'.join(DEFAULT_FLOWS)}> \"<title>\"")
    cfg = load_config()
    kind, title = args[0], " ".join(args[1].split())  # one line, keeps frontmatter valid
    nums = [int(m.group(1)) for p in TICKETS.glob("*.md")
            if (m := re.match(rf"{cfg['prefix']}-(\d+)-", p.name))]
    tid = f"{cfg['prefix']}-{max(nums, default=0) + 1}"
    slug = re.sub(r"[^a-z0-9]+", "-", title.lower()).strip("-")[:40] or "ticket"
    path = TICKETS / f"{tid}-{slug}.md"
    path.write_text(TEMPLATE.format(id=tid, type=kind, title=title))
    meta, body = parse(path)
    write(path, meta, log(meta, body, "created → backlog"))
    print(path)


def cmd_board(_):
    by_status = {}
    for p in sorted(TICKETS.glob("*.md")):
        meta, _ = parse(p)
        by_status.setdefault(meta["status"], []).append(meta)
    if not by_status:
        print("board is empty, create a ticket with `new`")
    for col in BOARD_COLUMNS + sorted(set(by_status) - set(BOARD_COLUMNS)):
        if col in by_status:
            print(f"\n{col.upper()} ({len(by_status[col])})")
            for t in by_status[col]:
                flag = " [blocked]" if t.get("blocked") == "true" else ""
                print(f"  {t['id']:<10} {t['type']:<6} {t['title']}{flag}")


def prerequisite(cfg, meta, stage):
    flow = cfg["flows"][meta["type"]]
    if stage not in flow:
        die(f"{meta['type']} tickets don't go through {stage} (flow: {' → '.join(flow)})")
    i = flow.index(stage)
    return "backlog" if i == 0 else STAGES[flow[i - 1]][1]


def cmd_start(args):
    stage, tid = args
    if stage not in STAGES:
        die(f"unknown stage {stage} (MVP has: {', '.join(STAGES)})")
    cfg = load_config()
    path = find(tid)
    meta, body = parse(path)
    running, _, _ = STAGES[stage]
    allowed = {prerequisite(cfg, meta, stage), running}
    if stage == "build":
        allowed.add("refined")  # bounce-backs from review/qa land here
    if meta["status"] not in allowed:
        die(f"{tid} is '{meta['status']}', {stage} needs one of: {', '.join(sorted(allowed))}")

    if stage == "build":
        for p in TICKETS.glob("*.md"):
            m, _ = parse(p)
            if m["id"] != tid and m["status"] == "in-progress":
                die(f"{m['id']} is already in-progress, finish it first (solo: one at a time)")
        branch = meta.get("branch") or path.stem
        exists = sh(f"git rev-parse --verify --quiet refs/heads/{branch}").returncode == 0
        git("checkout", *([] if exists else ["-b"]), branch)
        meta["branch"] = branch

    resumed = meta["status"] == running
    if not resumed:
        body = log(meta, body, f"{meta['status']} → {running} ({stage})")
        meta["status"] = running
    write(path, meta, body)

    executor = cfg["stages"].get(stage, {})
    print(f"TICKET: {tid}\nPATH: {path}\nSTAGE: {stage}\nRESUMED: {'yes' if resumed else 'no'}")
    if meta.get("branch"):
        print(f"BRANCH: {meta['branch']}")
    print("EXECUTOR: " + json.dumps(executor))
    for name in ("Review notes", "QA notes"):
        if stage == "build" and section(body, name):
            print(f"\n### Bounce-back: address these {name}\n{section(body, name)}")

    env = ticket_env(meta, path)
    cap = cfg["context_max_chars"]
    for c in cfg["context"] + cfg["context_by_stage"].get(stage, []):
        r = sh(c, env)
        out = (r.stdout + r.stderr).strip()
        if len(out) > cap:
            out = out[:cap] + f"\n… [truncated at {cap} chars]"
        print(f"\n### Context: {c}" + (f" (exit {r.returncode})" if r.returncode else "") + f"\n{out}")


def builtin_gate(cfg, stage, meta, body):
    """Structural checks. Always block: the next stage can't work without these outputs."""
    problems = []
    if stage == "refine":
        if not re.search(r"^- \[[ x]\] \S", section(body, "Acceptance criteria"), re.M):
            problems.append("Acceptance criteria needs at least one '- [ ] …' item")
        if not section(body, "Technical notes"):
            problems.append("Technical notes is empty")
        if not meta.get("points", "").isdigit():
            problems.append("frontmatter 'points' not set")
    if stage == "build":
        id_re = f"{meta['id']}([^0-9]|$)"  # PROJ-1 must not match PROJ-12
        if not sh(f"git log {cfg['base_branch']}..HEAD --oneline -E --grep='{id_re}'").stdout.strip():
            problems.append(f"no commit on {meta['branch']} mentions {meta['id']}")
        if sh("git status --porcelain -- . ':!.team'").stdout.strip():
            problems.append("uncommitted changes outside .team/")
        if not section(body, "Implementation notes"):
            problems.append("Implementation notes is empty")
    return problems


def cmd_finish(args):
    stage, tid = args
    if stage not in STAGES:
        die(f"unknown stage {stage}")
    cfg = load_config()
    path = find(tid)
    meta, body = parse(path)
    running, passed, failed = STAGES[stage]
    if meta["status"] != running:
        die(f"{tid} is '{meta['status']}', not '{running}'. Run `start {stage} {tid}` first")

    problems = builtin_gate(cfg, stage, meta, body)
    warnings = []
    gate = cfg["gates"].get(stage)
    if gate and not problems:
        r = sh(gate["run"], ticket_env(meta, path))
        if r.returncode:
            msg = f"gate `{gate['run']}` exited {r.returncode}\n{(r.stdout + r.stderr).strip()[-2000:]}"
            mode = gate.get("mode", cfg["gate_default_mode"])
            (problems if mode == "block" else warnings).append(msg)

    for w in warnings:
        print(f"WARN (advancing anyway, gate mode is warn): {w}")
        body = log(meta, body, f"WARN {stage} gate failed: {gate['run']}")
    if problems:
        body = log(meta, body, f"{running} → {failed} ({stage} gate failed: {problems[0].splitlines()[0]})")
        meta["status"] = failed
        write(path, meta, body)
        print(f"FAIL: {tid} → {failed}")
        for p in problems:
            print(f"  - {p}")
        sys.exit(1)
    body = log(meta, body, f"{running} → {passed}")
    meta["status"] = passed
    write(path, meta, body)
    print(f"PASS: {tid} → {passed}")


def main():
    cmds = {"init": cmd_init, "new": cmd_new, "board": cmd_board,
            "start": cmd_start, "finish": cmd_finish}
    if len(sys.argv) < 2 or sys.argv[1] not in cmds:
        die(__doc__)
    args = sys.argv[2:]
    if sys.argv[1] in ("start", "finish") and len(args) != 2:
        die(f"usage: {sys.argv[1]} <stage> <ID>")
    cmds[sys.argv[1]](args)


if __name__ == "__main__":
    main()
