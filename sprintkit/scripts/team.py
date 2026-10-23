#!/usr/bin/env python3
"""sprintkit runner: all bookkeeping, zero tokens. See docs/stage-contract.md.

  team.py init [--prefix PROJ]
  team.py new <story|bug|chore|spike> "<title>"
  team.py board                  # text board
  team.py serve [--port 7700]    # live board in the browser
  team.py queue [add|remove <ID>]  # sprint queue for the autopilot
  team.py next                   # next (stage, ticket) for the autopilot
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
QUEUE = TEAM / "queue.json"

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
    "autopilot": {"max_attempts": 2},
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


def ticket_files():
    """Ticket files in ID order: SK-2 before SK-10."""
    def number(p):
        m = re.match(r".*?-(\d+)-", p.name)
        return int(m.group(1)) if m else 0
    return sorted(TICKETS.glob("*.md"), key=number)


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
    print(create_ticket(load_config(), args[0], args[1]))


def create_ticket(cfg, kind, title, description=""):
    title = " ".join(title.split())  # one line, keeps frontmatter valid
    if kind not in DEFAULT_FLOWS or not title:
        raise ValueError(f"type must be one of {', '.join(DEFAULT_FLOWS)} and title non-empty")
    nums = [int(m.group(1)) for p in TICKETS.glob("*.md")
            if (m := re.match(rf"{cfg['prefix']}-(\d+)-", p.name))]
    tid = f"{cfg['prefix']}-{max(nums, default=0) + 1}"
    slug = re.sub(r"[^a-z0-9]+", "-", title.lower()).strip("-")
    if len(slug) > 40:
        slug = slug[:41].rsplit("-", 1)[0]
    slug = slug or "ticket"
    path = TICKETS / f"{tid}-{slug}.md"
    text = TEMPLATE.format(id=tid, type=kind, title=title)
    if description.strip():
        text = text.replace("## Description\n", f"## Description\n{description.strip()}\n", 1)
    path.write_text(text)
    meta, body = parse(path)
    write(path, meta, log(meta, body, "created → backlog"))
    return path


def cmd_board(_):
    by_status = {}
    for p in ticket_files():
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


def allowed_statuses(cfg, meta, stage):
    allowed = {prerequisite(cfg, meta, stage), STAGES[stage][0]}
    if stage == "build":
        allowed.add("refined")  # bounce-backs from review/qa land here
    return allowed


def next_stage(cfg, meta):
    """The stage this ticket can run now, or None (e.g. waiting on a stage not built yet)."""
    for stage in cfg["flows"].get(meta["type"], []):
        if stage in STAGES and meta["status"] in allowed_statuses(cfg, meta, stage):
            return stage
    return None


def cmd_start(args):
    stage, tid = args
    if stage not in STAGES:
        die(f"unknown stage {stage} (MVP has: {', '.join(STAGES)})")
    cfg = load_config()
    path = find(tid)
    meta, body = parse(path)
    running, _, _ = STAGES[stage]
    allowed = allowed_statuses(cfg, meta, stage)
    if meta["status"] not in allowed:
        die(f"{tid} is '{meta['status']}', {stage} needs one of: {', '.join(sorted(allowed))}")

    if stage == "build":
        for p in TICKETS.glob("*.md"):
            m, _ = parse(p)
            if m["id"] != tid and m["status"] == "in-progress":
                die(f"{m['id']} is already in-progress, finish it first (solo: one at a time)")
        branch = meta.get("branch") or path.stem
        exists = sh(f"git rev-parse --verify --quiet refs/heads/{branch}").returncode == 0
        git("checkout", branch) if exists else git("checkout", "-b", branch, cfg["base_branch"])
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
            out = (r.stdout + r.stderr).strip()
            if len(out) > 3000:  # real errors are often at the top (xcodebuild), summaries at the bottom
                out = out[:1500] + "\n… [middle truncated] …\n" + out[-1500:]
            msg = f"gate `{gate['run']}` exited {r.returncode}\n{out}"
            mode = gate.get("mode", cfg["gate_default_mode"])
            (problems if mode == "block" else warnings).append(msg)

    for w in warnings:
        print(f"WARN (advancing anyway, gate mode is warn): {w}")
        body = log(meta, body, f"WARN {stage} gate failed: {gate['run']}")
    if problems:
        reason = "user gate failed" if problems[0].startswith("gate `") else problems[0]
        body = log(meta, body, f"{stage} gate failed → {failed}: {reason.splitlines()[0][:100]}")
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


# ---------- sprint queue + autopilot ----------

def read_queue():
    return json.loads(QUEUE.read_text()) if QUEUE.exists() else []


def queue_add(tid):
    path = find(tid)
    q = read_queue()
    if tid not in q:
        q.append(tid)
        QUEUE.write_text(json.dumps(q) + "\n")
    meta, body = parse(path)
    meta["blocked"] = "false"  # re-queueing a blocked ticket means "try again"
    write(path, meta, log(meta, body, "queued"))


def queue_remove(tid, q=None):
    q = read_queue() if q is None else q
    if tid in q:
        q.remove(tid)
        QUEUE.write_text(json.dumps(q) + "\n")


def cmd_queue(args):
    if len(args) == 2 and args[0] in ("add", "remove"):
        (queue_add if args[0] == "add" else queue_remove)(args[1])
    elif args:
        die("usage: queue [add|remove <ID>]")
    print(" ".join(read_queue()) or "queue is empty")


def failed_attempts(body, stage):
    """Failures of this stage since the ticket was last queued or last passed it."""
    count = 0
    passed = STAGES[stage][1]
    for line in section(body, "Log").splitlines():
        if line.endswith(" queued") or f"→ {passed}" in line.split(" gate failed")[0]:
            count = 0
        elif f" {stage} gate failed" in line:
            count += 1
    return count


def block(path, meta, body, reason):
    meta["blocked"] = "true"
    write(path, meta, log(meta, body, f"blocked: {reason}"))


def cmd_next(_):
    cfg = load_config()
    limit = cfg["autopilot"].get("max_attempts", 2)
    q = read_queue()
    for tid in list(q):
        hits = list(TICKETS.glob(f"{tid}-*.md"))
        if not hits:
            queue_remove(tid, q)
            print(f"DEQUEUED: {tid} (ticket file is gone)")
            continue
        meta, body = parse(hits[0])
        stage = next_stage(cfg, meta)
        reason = None
        if not stage:
            queue_remove(tid, q)
            print(f"DEQUEUED: {tid} is '{meta['status']}', nothing more the autopilot can run")
            continue
        if cfg["stages"].get(stage, {}).get("human"):
            reason = f"{stage} is set to a human executor"
        elif (n := failed_attempts(body, stage)) >= limit:
            reason = f"{stage} gate failed {n}x, needs a look"
        if reason:
            block(hits[0], meta, body, reason)
            queue_remove(tid, q)
            print(f"BLOCKED: {tid} ({reason})")
            continue
        print(f"NEXT: {stage} {tid}")
        return
    print("NEXT: none")


def ticket_json(cfg, path, queue=()):
    meta, body = parse(path)
    log_lines = section(body, "Log").splitlines()
    last = log_lines[-1][2:] if log_lines else ""
    stage = next_stage(cfg, meta)
    return {**meta, "body": body, "last": last,
            "failed": "gate failed" in last or meta.get("blocked") == "true",
            "queued": queue.index(meta["id"]) + 1 if meta["id"] in queue else 0,
            "next": f"/sprintkit:{stage} {meta['id']}" if stage else ""}


def cmd_serve(args):
    from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
    import wizard
    port = int(args[args.index("--port") + 1]) if "--port" in args else 7700
    here = Path(__file__).parent
    board, setup = (here / "board.html").read_bytes(), (here / "setup.html").read_bytes()

    class Handler(BaseHTTPRequestHandler):
        def reply(self, code, body, ctype="application/json"):
            data = body if isinstance(body, bytes) else json.dumps(body).encode()
            self.send_response(code)
            self.send_header("Content-Type", ctype)
            self.send_header("Content-Length", str(len(data)))
            self.send_header("Cache-Control", "no-store")
            self.end_headers()
            self.wfile.write(data)

        def is_local(self):
            # DNS-rebinding guard: a remote page can resolve its own domain to 127.0.0.1,
            # but its requests still carry that domain in Host.
            if (self.headers.get("Host") or "").rsplit(":", 1)[0] in ("127.0.0.1", "localhost"):
                return True
            self.reply(403, {"error": "forbidden host"})
            return False

        def do_GET(self):
            self.path = self.path.split("?", 1)[0]  # route on the path; /?saved=1 is still /
            if not self.is_local():
                return
            if self.path == "/":  # no config yet → the setup wizard, afterwards the board
                return self.reply(200, board if CONFIG.exists() else setup, "text/html; charset=utf-8")
            if self.path == "/settings":  # same page as setup, in settings mode
                return self.reply(200, setup, "text/html; charset=utf-8")
            if self.path == "/api/setup":
                return self.reply(200, {**wizard.discover(Path.cwd()), "configured": CONFIG.exists(),
                                        "config": wizard.read_json(CONFIG)})
            if self.path != "/api/tickets":
                return self.reply(404, {"error": "not found"})
            try:
                cfg, queue = load_config(), read_queue()
                tickets = [ticket_json(cfg, p, queue) for p in ticket_files()]
            except (SystemExit, ValueError) as e:  # a file mid-write or hand-broken; next poll retries
                return self.reply(500, {"error": str(getattr(e, "code", e))})
            self.reply(200, {"prefix": cfg["prefix"], "columns": BOARD_COLUMNS,
                             "tickets": tickets, "queue": queue})

        def do_POST(self):
            self.path = self.path.split("?", 1)[0]
            if not self.is_local():
                return
            # Browsers can't send application/json cross-origin without a CORS preflight,
            # which this server never approves, so other sites can't plant tickets for agents to read.
            if self.path not in ("/api/tickets", "/api/queue", "/api/setup", "/api/settings") or \
                    self.headers.get("Content-Type", "").split(";")[0] != "application/json":
                return self.reply(400, {"error": "POST application/json to /api/tickets, /api/queue, "
                                                 "/api/setup or /api/settings"})
            if self.path in ("/api/setup", "/api/settings"):
                # setup only before there's a config, settings only after
                if CONFIG.exists() == (self.path == "/api/setup"):
                    return self.reply(409, {"error": "already set up" if CONFIG.exists() else "not set up yet"})
                action = wizard.apply if self.path == "/api/setup" else wizard.update
                try:
                    data = json.loads(self.rfile.read(int(self.headers.get("Content-Length", 0))))
                    return self.reply(200, {"steps": action(Path.cwd(), data, CONFIG)})
                except ValueError as e:
                    return self.reply(400, {"error": str(e)})
            try:
                data = json.loads(self.rfile.read(int(self.headers.get("Content-Length", 0))))
                if not isinstance(data, dict):
                    raise ValueError("expected a JSON object")
                cfg = load_config()
                if self.path == "/api/queue":
                    tid = str(data.get("id", ""))
                    if not re.fullmatch(r"[A-Za-z0-9_-]+-\d+", tid):
                        raise ValueError("bad ticket id")
                    if data.get("action") == "remove":
                        queue_remove(tid)
                    else:
                        queue_add(tid)
                    return self.reply(200, {"queue": read_queue()})
                path = create_ticket(cfg, data.get("type", ""), str(data.get("title", "")),
                                     str(data.get("description", "")))
            except ValueError as e:
                return self.reply(400, {"error": str(e)})
            except SystemExit as e:  # find() on an unknown id
                return self.reply(404, {"error": str(e.code)})
            self.reply(201, ticket_json(cfg, path, read_queue()))

        def log_message(self, *_):
            pass

    try:
        server = ThreadingHTTPServer(("127.0.0.1", port), Handler)
    except OSError:
        print(f"port {port} is in use. If the board is already running, it's at http://127.0.0.1:{port}")
        return
    print(f"sprintkit board: http://127.0.0.1:{server.server_port}", flush=True)
    server.serve_forever()


def main():
    cmds = {"init": cmd_init, "new": cmd_new, "board": cmd_board,
            "start": cmd_start, "finish": cmd_finish, "serve": cmd_serve,
            "queue": cmd_queue, "next": cmd_next}
    if len(sys.argv) < 2 or sys.argv[1] not in cmds:
        die(__doc__)
    args = sys.argv[2:]
    if sys.argv[1] in ("start", "finish") and len(args) != 2:
        die(f"usage: {sys.argv[1]} <stage> <ID>")
    cmds[sys.argv[1]](args)


if __name__ == "__main__":
    main()
