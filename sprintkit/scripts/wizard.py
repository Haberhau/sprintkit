"""Setup wizard backend: find what's installed and detectable, then apply the chosen setup.

Used by `team.py serve` while the project has no .team/config.json.
Every git/gh call takes an argument list, never a shell string: names typed into the
wizard must not reach a shell.
"""
import json
import re
import shlex
import shutil
import subprocess
from pathlib import Path

PLUGIN_ROOT = Path(__file__).resolve().parent.parent
STAGE_SLOTS = ["refine", "build", "review", "qa"]
NAME = re.compile(r"[\w:.-]+")
PLUGIN_ID = re.compile(r"[\w.-]+@[\w.-]+")
REPO_URL = re.compile(r"(https://github\.com/|git@github\.com:)[\w.-]+/[\w.-]+?(\.git)?")
REPO_NAME = re.compile(r"([\w.-]+/)?[\w.-]+")


def run(*cmd, cwd=None):
    try:
        r = subprocess.run(cmd, cwd=cwd, capture_output=True, text=True, timeout=120)
    except (OSError, subprocess.TimeoutExpired) as e:
        return 1, str(e)
    return r.returncode, (r.stdout + r.stderr).strip()


def read_json(path):
    try:
        return json.loads(Path(path).read_text())
    except (OSError, ValueError):
        return {}


# ---------- discovery ----------

def frontmatter(path):
    m = re.match(r"---\n(.*?)\n---", path.read_text(errors="replace"), re.S)
    meta = {}
    for line in (m.group(1).splitlines() if m else []):
        k, sep, v = line.partition(":")
        if sep and not line[:1].isspace():
            meta[k.strip()] = v.strip().strip("\"'")
    return meta


def components(root, prefix=""):
    """Agents and skills under a plugin or .claude folder, named the way Claude Code addresses them."""
    def entry(path, fallback):
        fm = frontmatter(path)
        desc = fm.get("description", "")
        return {"id": prefix + (fm.get("name") or fallback),
                "description": "" if desc in ("|", ">", "|-", ">-") else desc[:200]}
    root = Path(root)
    agents = [entry(p, p.stem) for p in sorted(root.glob("agents/*.md"))]
    skills = [entry(p, p.parent.name) for p in sorted(root.glob("skills/**/SKILL.md"))]
    return agents, skills


def suggest_prefix(folder_name):
    words = re.findall(r"[A-Za-z0-9]+", folder_name)
    if len(words) > 1:
        return "".join(w[0] for w in words)[:4].upper()
    return (words[0] if words else "PROJ")[:4].upper()


def newest_iphone_simulator():
    code, out = run("xcrun", "simctl", "list", "devices", "available", "-j")
    if code:
        return None
    best = None
    for runtime, devices in json.loads(out).get("devices", {}).items():
        m = re.search(r"iOS-(\d+)-(\d+)", runtime)
        phones = [d for d in devices if d.get("name", "").startswith("iPhone")]
        if m and phones and (best is None or (int(m[1]), int(m[2])) > best[0]):
            best = ((int(m[1]), int(m[2])), phones[0])
    return best[1] if best else None


def detect_checks(cwd):
    """Test/lint commands this project already has, as gate suggestions."""
    checks = []
    scripts = read_json(cwd / "package.json").get("scripts", {})
    for script, label in (("test", "package.json test script"), ("lint", "package.json lint script")):
        if script in scripts:
            checks.append({"run": "npm test" if script == "test" else "npm run lint", "why": label})
    if any((cwd / f).exists() for f in ("pyproject.toml", "pytest.ini")) or (cwd / "tests").is_dir():
        checks.append({"run": "python3 -m pytest", "why": "Python project"})
    if (cwd / "Cargo.toml").exists():
        checks.append({"run": "cargo test", "why": "Cargo.toml"})
    if (cwd / "go.mod").exists():
        checks.append({"run": "go test ./...", "why": "go.mod"})
    if (cwd / "Package.swift").exists():
        checks.append({"run": "swift test", "why": "Swift package (Package.swift)"})
    if (cwd / "Makefile").exists() and re.search(r"^test:", (cwd / "Makefile").read_text(errors="replace"), re.M):
        checks.append({"run": "make test", "why": "Makefile test target"})
    for proj in sorted(cwd.glob("*.xcodeproj"))[:1]:
        sim = newest_iphone_simulator()
        # by simulator ID: a name like "iPhone 16 Pro" can resolve to an iOS version below the deployment target
        dest = f" -destination 'id={sim['udid']}'" if sim else ""
        why = f"Xcode project, newest simulator: {sim['name']}" if sim else "Xcode project (no iPhone simulator found)"
        checks.append({"run": f"xcodebuild test -scheme {shlex.quote(proj.stem)}{dest}", "why": why})
    return checks


def tool_missing(cmd):
    """True if a context command's program isn't on PATH, so the command would only produce an error."""
    try:
        words = shlex.split(cmd)
    except ValueError:
        return False
    words = [w for w in words if "=" not in w.split("/")[0]]  # skip leading VAR=value assignments
    return bool(words) and shutil.which(words[0]) is None


def discover(cwd):
    home = Path.home()
    user_on = read_json(home / ".claude/settings.json").get("enabledPlugins", {})
    project_on = {**read_json(cwd / ".claude/settings.json").get("enabledPlugins", {}),
                  **read_json(cwd / ".claude/settings.local.json").get("enabledPlugins", {})}
    plugins = []
    for pid, installs in sorted(read_json(home / ".claude/plugins/installed_plugins.json").get("plugins", {}).items()):
        if not installs or pid.split("@")[0] == "sprintkit":
            continue
        name = pid.split("@")[0]
        agents, skills = components(installs[0].get("installPath", ""), f"{name}:")
        plugins.append({"id": pid, "name": name, "enabled": bool(project_on.get(pid, user_on.get(pid, False))),
                        "agents": agents, "skills": skills})

    git_ok = run("git", "rev-parse", "--is-inside-work-tree", cwd=cwd)[0] == 0
    remote = run("git", "remote", "get-url", "origin", cwd=cwd) if git_ok else (1, "")
    gh = shutil.which("gh") is not None
    context = []
    if shutil.which("graphify"):
        note = "" if (cwd / "graphify-out").exists() else " Run `graphify update .` once to build the graph."
        context.append({"run": 'graphify query "$TICKET_TITLE"', "why": "graphify is installed." + note, "on": True})
    if (cwd / ".git").exists():
        context.append({"run": "git log --oneline -15", "why": "Recent commits, so executors see what changed lately.", "on": False})
    configured = read_json(cwd / ".team/config.json").get("context", [])

    sk_agents, _ = components(PLUGIN_ROOT, "sprintkit:")  # its skills are stage commands, not executors
    user_agents, user_skills = components(home / ".claude")
    proj_agents, proj_skills = components(cwd / ".claude")
    return {
        "contextMissing": [c for c in dict.fromkeys(configured + [o["run"] for o in context]) if tool_missing(c)],
        "folder": str(cwd), "folderName": cwd.name, "prefix": suggest_prefix(cwd.name),
        "git": {"isRepo": git_ok,
                "hasCommits": git_ok and run("git", "rev-parse", "--verify", "HEAD", cwd=cwd)[0] == 0,
                "branch": run("git", "symbolic-ref", "--short", "HEAD", cwd=cwd)[1] if git_ok else "main",
                "remote": remote[1] if remote[0] == 0 else ""},
        "gh": {"installed": gh, "authed": gh and run("gh", "auth", "status")[0] == 0},
        "sprintkit": {"agents": sk_agents},
        "plugins": plugins,
        "user": {"agents": user_agents, "skills": user_skills},
        "project": {"agents": proj_agents, "skills": proj_skills},
        "checks": detect_checks(cwd), "context": context,
        "defaults": {"refine": {"agent": "sprintkit:tech-lead"}, "build": {"agent": "sprintkit:developer"},
                     "review": {"agent": "sprintkit:reviewer"}, "qa": {"agent": "sprintkit:qa-engineer"}},
    }


# ---------- apply ----------

def executor(stage, ex):
    """One stage executor, in any form the stage contract allows. {} means "not set"."""
    if not isinstance(ex, dict):
        raise ValueError(f"bad executor for {stage}")
    if not ex:
        return None
    if ex == {"human": True}:
        return ex
    if set(ex) == {"command"} and str(ex["command"]).strip():
        return {"command": str(ex["command"]).strip()}
    kind = "agent" if "agent" in ex else "skill" if "skill" in ex else None
    skills = ex.get("skills", [])
    if kind and not set(ex) - {kind, "skills"} and NAME.fullmatch(str(ex[kind])) \
            and isinstance(skills, list) and all(NAME.fullmatch(str(x)) for x in skills):
        return dict(ex)
    raise ValueError(f"bad executor for {stage}")


def validate(data):
    if not isinstance(data, dict):
        raise ValueError("expected a JSON object")
    prefix = str(data.get("prefix", ""))
    if not re.fullmatch(r"[A-Z][A-Z0-9]{0,9}", prefix):
        raise ValueError("prefix: 1-10 capital letters or digits, starting with a letter")
    stages = {}
    for stage, ex in (data.get("stages") or {}).items():
        if stage not in STAGE_SLOTS:
            raise ValueError(f"unknown stage {stage}")
        if checked := executor(stage, ex):
            stages[stage] = checked
    context = [str(c) for c in data.get("context") or [] if str(c).strip()]
    gates = {}
    for stage, g in (data.get("gates") or {}).items():
        if stage not in STAGE_SLOTS or not str(g.get("run", "")).strip() or g.get("mode") not in ("warn", "block"):
            raise ValueError(f"bad gate for {stage}")
        gates[stage] = {"run": str(g["run"]).strip(), "mode": g["mode"]}
    plugins = data.get("plugins") or {}
    if not all(PLUGIN_ID.fullmatch(str(k)) and isinstance(v, bool) for k, v in plugins.items()):
        raise ValueError("bad plugin toggles")
    gh = data.get("github") or {"mode": "skip"}
    if gh.get("mode") == "link" and not REPO_URL.fullmatch(str(gh.get("url", ""))):
        raise ValueError("GitHub URL should look like https://github.com/owner/repo")
    if gh.get("mode") == "create" and (not REPO_NAME.fullmatch(str(gh.get("name", "")))
                                       or gh.get("visibility") not in ("private", "public")):
        raise ValueError("repo name: letters, digits, . _ - (optionally owner/name)")
    if gh.get("mode") not in ("link", "create", "skip", "keep"):
        raise ValueError("bad GitHub option")
    return prefix, stages, context, gates, plugins, gh


def apply(cwd, data, config_path):
    """Validate everything first, then act: local changes before GitHub, so a GitHub failure
    still leaves a working project."""
    prefix, stages, context, gates, plugins, gh = validate(data)
    steps = []

    def step(ok, msg):
        steps.append({"ok": ok, "msg": msg})
        return ok

    if run("git", "rev-parse", "--is-inside-work-tree", cwd=cwd)[0]:
        code, out = run("git", "init", "-b", "main", cwd=cwd)
        if not step(code == 0, "git init" if code == 0 else f"git init failed: {out}"):
            return steps
    if run("git", "rev-parse", "--verify", "HEAD", cwd=cwd)[0]:
        # branches for tickets are cut from the base branch, which needs a first commit
        code, out = run("git", "commit", "--allow-empty", "-m", "Initial commit", cwd=cwd)
        if not step(code == 0, "initial commit" if code == 0 else f"initial commit failed: {out}"):
            return steps
    base = run("git", "symbolic-ref", "--short", "HEAD", cwd=cwd)[1] or "main"

    config = {"prefix": prefix, "base_branch": base, "stages": stages, "context": context,
              "gates": gates, "gate_default_mode": "warn"}
    (cwd / ".team/tickets").mkdir(parents=True, exist_ok=True)
    (cwd / config_path).write_text(json.dumps(config, indent=2) + "\n")
    step(True, "wrote .team/config.json")
    ignore_team(cwd, step)

    write_plugins(cwd, plugins, step)
    build_graph(cwd, context, step)
    connect_github(cwd, gh, step)
    return steps


def ignore_team(cwd, step):
    """.team/ is local state: tracked ticket files block branch switches once main has newer ones (SK-13)."""
    if run("git", "ls-files", "--error-unmatch", ".team", cwd=cwd)[0] == 0:
        return  # the project tracks its tickets on purpose; leave it
    gi = cwd / ".gitignore"
    lines = gi.read_text().splitlines() if gi.exists() else []
    if not {".team", ".team/", "/.team", "/.team/"} & set(lines):
        gi.write_text("\n".join(lines + [".team/"]) + "\n")
        step(True, "added .team/ to .gitignore")


def build_graph(cwd, context, step):
    """graphify as a context provider needs a graph to query; build it once (AST only, no tokens)."""
    if any(c.startswith("graphify") for c in context) and not (cwd / "graphify-out").exists():
        code, out = run("graphify", "update", ".", cwd=cwd)
        step(code == 0, "built the graphify graph" if code == 0 else f"graphify update failed: {out[-200:]}")


def update(cwd, data, config_path):
    """Settings tab: change what the screen shows, keep everything else in the config."""
    existing = read_json(cwd / config_path)
    _, stages, context, gates, plugins, gh = validate({**data, "prefix": existing.get("prefix", "")})
    attempts = (data.get("autopilot") or {}).get("max_attempts", 2)
    if not isinstance(attempts, int) or not 1 <= attempts <= 10:
        raise ValueError("autopilot attempts: a whole number from 1 to 10")
    steps = []

    def step(ok, msg):
        steps.append({"ok": ok, "msg": msg})

    # the screen edits only the build gate; gates for other stages were set by hand, keep them
    kept_gates = {k: v for k, v in existing.get("gates", {}).items() if k != "build"}
    config = {**existing, "stages": stages, "context": context, "gates": {**kept_gates, **gates},
              "autopilot": {**existing.get("autopilot", {}), "max_attempts": attempts}}
    (cwd / config_path).write_text(json.dumps(config, indent=2) + "\n")
    step(True, "saved .team/config.json")
    write_plugins(cwd, plugins, step)
    build_graph(cwd, context, step)
    connect_github(cwd, gh, step)
    return steps


def write_plugins(cwd, plugins, step):
    if not plugins:
        return
    settings_path = cwd / ".claude/settings.json"
    settings = read_json(settings_path)  # keep everything else in the file
    settings.setdefault("enabledPlugins", {}).update(plugins)
    settings_path.parent.mkdir(exist_ok=True)
    settings_path.write_text(json.dumps(settings, indent=2) + "\n")
    off = [k for k, v in plugins.items() if not v]
    step(True, f"wrote .claude/settings.json ({len(plugins) - len(off)} plugins on, {len(off)} off for this project)")


def connect_github(cwd, gh, step):
    if gh["mode"] == "link":
        code, out = run("git", "remote", "add", "origin", gh["url"], cwd=cwd)
        step(code == 0, f"linked origin → {gh['url']}" if code == 0 else f"linking GitHub failed: {out}")
    elif gh["mode"] == "create":
        code, out = run("gh", "repo", "create", gh["name"], f"--{gh['visibility']}",
                        "--source", ".", "--remote", "origin", "--push", cwd=cwd)
        step(code == 0, f"created {gh['visibility']} GitHub repo {gh['name']}" if code == 0
             else f"creating the GitHub repo failed: {out}")
