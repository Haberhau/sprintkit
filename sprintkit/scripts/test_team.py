"""End-to-end check of team.py in a throwaway git repo. Run: python3 test_team.py"""
import json
import re
import subprocess
import sys
import tempfile
from pathlib import Path

TEAM = Path(__file__).resolve().parent / "team.py"


def run(*args, ok=True):
    r = subprocess.run([sys.executable, str(TEAM), *args], capture_output=True, text=True)
    assert (r.returncode == 0) == ok, f"{args} -> {r.returncode}\n{r.stdout}{r.stderr}"
    return r.stdout + r.stderr


def sh(cmd):
    subprocess.run(cmd, shell=True, check=True, capture_output=True)


def status(path):
    return re.search(r"^status: (.+)$", path.read_text(), re.M).group(1)


def fill(path, name, text):
    s = path.read_text()
    path.write_text(s.replace(f"## {name}\n", f"## {name}\n{text}\n", 1))


def review(path, text):
    """Replace Review notes, as the reviewer does."""
    s = path.read_text()
    path.write_text(re.sub(r"(## Review notes\n).*?(?=## QA notes)", lambda m: f"{m.group(1)}{text}\n\n", s, flags=re.S))


def check_server():
    import urllib.error
    import urllib.request
    srv = subprocess.Popen([sys.executable, str(TEAM), "serve", "--port", "0"],
                           stdout=subprocess.PIPE, text=True)
    try:
        base = srv.stdout.readline().split()[-1]

        def req(path, data=None, ctype="application/json", host=None):
            r = urllib.request.Request(base + path, data=data, headers={"Content-Type": ctype})
            if host:
                r.add_unredirected_header("Host", host)
            try:
                with urllib.request.urlopen(r) as resp:
                    return resp.status, resp.read()
            except urllib.error.HTTPError as e:
                return e.code, e.read()

        code, page = req("/")
        assert code == 200 and b"sprintkit board" in page
        assert req("/?saved=1")[0] == 200  # query strings don't break routing
        code, body = req("/api/tickets")
        data = json.loads(body)
        by_id = {t["id"]: t for t in data["tickets"]}
        assert by_id["APP-1"]["status"] == "in-review" and by_id["APP-1"]["next"] == "/sprintkit:review APP-1"
        assert by_id["APP-2"]["failed"]  # its last log line is the blocked build gate
        assert not by_id["APP-3"]["failed"] and by_id["APP-3"]["next"] == "/sprintkit:build APP-3"

        code, body = req("/api/tickets", json.dumps({"type": "story", "title": "From the board",
                                                      "description": "made in the UI"}).encode())
        made = json.loads(body)
        assert code == 201 and made["id"] == "APP-4" and made["next"] == "/sprintkit:refine APP-4"
        assert "made in the UI" in made["body"]

        # a cross-site form post (no JSON content type) and a rebound Host are refused
        assert req("/api/tickets", b"type=story&title=x", "application/x-www-form-urlencoded")[0] == 400
        assert req("/api/tickets", host="evil.example:80")[0] == 403
        assert req("/api/tickets", json.dumps({"type": "nope", "title": "x"}).encode())[0] == 400

        # queue from the board
        code, body = req("/api/queue", json.dumps({"id": "APP-4", "action": "add"}).encode())
        assert code == 200 and json.loads(body)["queue"] == ["APP-4"]
        tickets = {t["id"]: t for t in json.loads(req("/api/tickets")[1])["tickets"]}
        assert tickets["APP-4"]["queued"] == 1 and tickets["APP-1"]["queued"] == 0
        assert req("/api/queue", json.dumps({"id": "APP-99"}).encode())[0] == 404
        assert req("/api/queue", json.dumps({"id": "../../x"}).encode())[0] == 400
        # reorder (SK-10)
        req("/api/queue", json.dumps({"id": "APP-3", "action": "add"}).encode())
        code, body = req("/api/queue", json.dumps({"id": "APP-3", "action": "move", "to": 0}).encode())
        assert code == 200 and json.loads(body)["queue"] == ["APP-3", "APP-4"]
        assert req("/api/queue", json.dumps({"id": "APP-3", "action": "move", "to": "x"}).encode())[0] == 400
        assert req("/api/queue", json.dumps({"id": "APP-1", "action": "move", "to": 0}).encode())[0] == 400
        assert run("queue", "move", "APP-3", "2").strip() == "APP-4 APP-3"
        req("/api/queue", json.dumps({"id": "APP-3", "action": "remove"}).encode())
        code, body = req("/api/queue", json.dumps({"id": "APP-4", "action": "remove"}).encode())
        assert json.loads(body)["queue"] == []
    finally:
        srv.terminate()


def check_autopilot():
    import os
    with tempfile.TemporaryDirectory() as d:
        os.chdir(d)
        sh("git init -q -b main && git config user.email t@t && git config user.name t "
           "&& git commit -q --allow-empty -m init")
        run("init", "--prefix", "APP")
        run("new", "story", "Needs refining")
        run("new", "bug", "Quick fix")
        run("queue", "add", "APP-1")
        assert run("queue", "add", "APP-2").strip() == "APP-1 APP-2"

        # refine fails twice → blocked and dequeued, autopilot moves on
        for _ in range(2):
            assert run("next").strip() == "NEXT: refine APP-1"
            run("start", "refine", "APP-1")
            run("finish", "refine", "APP-1", ok=False)
        out = run("next")
        assert "BLOCKED: APP-1" in out and out.strip().endswith("NEXT: build APP-2")
        assert "blocked: true" in next(Path(".team/tickets").glob("APP-1-*")).read_text()
        assert run("queue").strip() == "APP-2"

        # bug builds and passes → dequeued, queue done
        run("start", "build", "APP-2")
        bug = next(Path(".team/tickets").glob("APP-2-*"))
        fill(bug, "Implementation notes", "Fixed.")
        sh("git commit -q --allow-empty -m 'APP-2 fix'")
        run("finish", "build", "APP-2")
        assert run("next").strip() == "NEXT: qa APP-2"
        run("queue", "remove", "APP-2")

        # next ticket's branch starts from main, not from APP-2's unreviewed branch
        run("new", "chore", "Other work")
        run("start", "build", "APP-3")
        assert subprocess.check_output(["git", "log", "--oneline", "main..HEAD"], text=True) == ""

        # re-queueing unblocks and resets the attempt counter; human executors get blocked
        run("queue", "add", "APP-1")
        assert "blocked: false" in next(Path(".team/tickets").glob("APP-1-*")).read_text()
        assert run("next").strip() == "NEXT: refine APP-1"
        cfg = json.loads(Path(".team/config.json").read_text())
        cfg["stages"]["refine"] = {"human": True}
        Path(".team/config.json").write_text(json.dumps(cfg))
        assert "BLOCKED: APP-1 (refine is set to a human executor)" in run("next")


def check_review():
    import os
    with tempfile.TemporaryDirectory() as d:
        os.chdir(d)
        sh("git init -q -b main && git config user.email t@t && git config user.name t "
           "&& git commit -q --allow-empty -m init")
        run("init", "--prefix", "APP")
        story = Path(run("new", "story", "Login form").strip())
        run("start", "refine", "APP-1")
        fill(story, "Acceptance criteria", "- [ ] user can log in")
        fill(story, "Technical notes", "Session middleware.")
        story.write_text(story.read_text().replace("blocked: false", "blocked: false\npoints: 2"))
        assert "NEXT: /sprintkit:build APP-1" in run("finish", "refine", "APP-1")
        run("start", "build", "APP-1")
        fill(story, "Implementation notes", "Added form.")
        Path("login.txt").write_text("form")
        sh("git add login.txt && git commit -q -m 'APP-1 login form'")
        assert "NEXT: /sprintkit:review APP-1" in run("finish", "build", "APP-1")
        run("queue", "add", "APP-1")
        assert run("next").strip() == "NEXT: review APP-1"

        # review checks out the branch and shows the diff; no verdict → rerun review, not rebuild
        sh("git checkout -q main")
        out = run("start", "review", "APP-1")
        assert "login.txt" in out and "BASE: main" in out
        assert subprocess.check_output(["git", "branch", "--show-current"], text=True).strip() == "APP-1-login-form"
        assert status(story) == "reviewing"
        review(story, "Looks fine.")
        assert "VERDICT" in run("finish", "review", "APP-1", ok=False)
        assert status(story) == "in-review"

        # changes → back to refined; the next build sees the review notes
        run("start", "review", "APP-1")
        review(story, "1. No test.\nVERDICT: changes")
        assert "asked for changes" in run("finish", "review", "APP-1", ok=False)
        assert status(story) == "refined"
        assert "Bounce-back: address these Review notes" in run("start", "build", "APP-1")
        sh("git commit -q --allow-empty -m 'APP-1 add test'")
        run("finish", "build", "APP-1")

        # rejected twice → the autopilot blocks it instead of ping-ponging build and review
        run("start", "review", "APP-1")
        review(story, "VERDICT: changes")
        run("finish", "review", "APP-1", ok=False)
        assert "BLOCKED: APP-1 (review gate failed 3x" in run("next")  # incl. the missing verdict

        # approve → in-qa, last verdict line wins
        run("queue", "add", "APP-1")
        run("start", "build", "APP-1")
        run("finish", "build", "APP-1")
        run("start", "review", "APP-1")
        review(story, "**VERDICT: approve**")
        out = run("finish", "review", "APP-1")
        assert "PASS: APP-1 → in-qa" in out and "NEXT: /sprintkit:qa APP-1" in out
        assert run("next").strip() == "NEXT: qa APP-1"

        # spikes and chores end at done (flow: refine → build, build)
        sh("git checkout -q main")
        spike = Path(run("new", "spike", "Pick a DB").strip())
        run("start", "refine", "APP-2")
        fill(spike, "Acceptance criteria", "- [ ] a recommendation is written down")
        fill(spike, "Technical notes", "Timebox 1 day.")
        spike.write_text(spike.read_text().replace("blocked: false", "blocked: false\npoints: 1"))
        run("finish", "refine", "APP-2")
        run("start", "build", "APP-2")
        fill(spike, "Implementation notes", "Use SQLite.")
        sh("git commit -q --allow-empty -m 'APP-2 decision record'")
        assert "PASS: APP-2 → done" in run("finish", "build", "APP-2")
        run("start", "review", "APP-2", ok=False)
        sh("git checkout -q main")
        chore = Path(run("new", "chore", "Bump deps").strip())
        run("start", "build", "APP-3")
        fill(chore, "Implementation notes", "Bumped.")
        sh("git commit -q --allow-empty -m 'APP-3 bump'")
        assert "PASS: APP-3 → done" in run("finish", "build", "APP-3")


def check_qa():
    import os
    with tempfile.TemporaryDirectory() as d:
        os.chdir(d)
        sh("git init -q -b main && git config user.email t@t && git config user.name t "
           "&& git commit -q --allow-empty -m init")
        run("init", "--prefix", "APP")
        git = lambda *a: subprocess.check_output(["git", *a], text=True).strip()

        def built_bug(title, n, file):
            sh("git checkout -q main")
            bug = Path(run("new", "bug", title).strip())
            run("start", "build", f"APP-{n}")
            fill(bug, "Implementation notes", "Fixed.")
            Path(file).write_text(f"fix {n}")
            sh(f"git add {file} && git commit -q -m 'APP-{n} fix'")
            assert f"NEXT: /sprintkit:qa APP-{n}" in run("finish", "build", f"APP-{n}")
            return bug

        # bug flow: build → qa. No AC ticked → back to refined, the next build sees the QA notes
        bug = built_bug("Crash on save", 1, "save.txt")
        sh("git checkout -q main")
        run("start", "qa", "APP-1")
        assert status(bug) == "testing" and git("branch", "--show-current") == "APP-1-crash-on-save"
        fill(bug, "QA notes", "Still crashes on empty file.")
        fill(bug, "Acceptance criteria", "- [x] saving no longer crashes\n- [ ] empty file saves")
        assert "every Acceptance criteria box" in run("finish", "qa", "APP-1", ok=False)
        assert status(bug) == "refined"
        assert "Bounce-back: address these QA notes" in run("start", "build", "APP-1")
        sh("git commit -q --allow-empty -m 'APP-1 handle empty file'")
        run("finish", "build", "APP-1")

        # uncommitted tests fail the gate; nothing is merged
        run("start", "qa", "APP-1")
        bug.write_text(bug.read_text().replace("- [ ] empty", "- [x] empty"))
        Path("test_save.txt").write_text("test")
        assert "uncommitted" in run("finish", "qa", "APP-1", ok=False)
        assert git("ls-tree", "main", "save.txt") == ""

        # pass → merged into main with --no-ff, ticket done, on main afterwards
        run("start", "build", "APP-1")
        sh("git add test_save.txt && git commit -q -m 'APP-1 test'")
        run("finish", "build", "APP-1")
        run("start", "qa", "APP-1")
        # a fake graphify on PATH: the runner refreshes the graph after the merge (SK-16)
        Path("bin").mkdir()
        Path("bin/graphify").write_text("#!/bin/sh\necho \"$@\" > .git/graph-updated\n")
        os.chmod("bin/graphify", 0o755)
        Path("graphify-out").mkdir()
        os.environ["PATH"] = f"{Path('bin').resolve()}:{os.environ['PATH']}"
        sh("echo bin/ >> .git/info/exclude")
        out = run("finish", "qa", "APP-1")
        assert "PASS: APP-1 → done" in out and "GRAPH: refreshed" in out
        assert Path(".git/graph-updated").read_text().strip() == "update ."
        os.environ["PATH"] = os.environ["PATH"].split(":", 1)[1]
        assert git("branch", "--show-current") == "main" and Path("save.txt").read_text() == "fix 1"
        assert git("log", "-1", "--format=%s") == "APP-1 Merge APP-1-crash-on-save"
        assert len(git("log", "-1", "--format=%P").split()) == 2  # a merge commit, not a fast-forward

        # conflict with main → merge aborted, ticket blocked in in-qa, main untouched
        bug2 = built_bug("Wrong total", 2, "total.txt")
        sh("git checkout -q main && echo other > total.txt && git add total.txt && git commit -q -m 'other change'")
        run("queue", "add", "APP-2")
        run("start", "qa", "APP-2")
        fill(bug2, "Acceptance criteria", "- [x] total is right")
        fill(bug2, "QA notes", "Checked.")
        out = run("finish", "qa", "APP-2", ok=False)
        assert "BLOCKED: APP-2" in out and "total.txt" in out
        assert status(bug2) == "in-qa" and "blocked: true" in bug2.read_text()
        assert git("branch", "--show-current") == "APP-2-wrong-total" and not git("status", "--porcelain", "--untracked-files=no")
        assert git("show", "main:total.txt") == "other" and run("queue").strip() == "queue is empty"

        # files untracked before a stage started don't count as its uncommitted work (SK-17)
        sh("git checkout -q main")
        Path("notes-before.txt").write_text("already here")
        chore = Path(run("new", "chore", "Tidy").strip())
        run("start", "build", "APP-3")
        fill(chore, "Implementation notes", "Tidied.")
        sh("git commit -q --allow-empty -m 'APP-3 tidy'")
        Path("forgot.txt").write_text("new during build")
        out = run("finish", "build", "APP-3", ok=False)
        assert "forgot.txt" in out and "notes-before.txt" not in out
        Path("forgot.txt").unlink()
        assert "READY: yes" in run("start", "build", "APP-3")  # resumed with passing output: no executor rerun
        Path("graphify-out/cache").mkdir(parents=True, exist_ok=True)
        Path("graphify-out/cache/new.json").write_text("{}")  # graph refreshed during the build: generated, not work
        assert "PASS: APP-3 → done" in run("finish", "build", "APP-3")


def check_gate_setup():
    import os
    with tempfile.TemporaryDirectory() as d:
        os.chdir(d)
        sh("git init -q -b main && git config user.email t@t && git config user.name t "
           "&& git commit -q --allow-empty -m init")
        run("init", "--prefix", "APP")
        chore = Path(run("new", "chore", "Bump").strip())
        run("queue", "add", "APP-1")
        run("start", "build", "APP-1")
        fill(chore, "Implementation notes", "Bumped.")
        sh("git commit -q --allow-empty -m 'APP-1 bump'")

        def gate(cmd):
            cfg = json.loads(Path(".team/config.json").read_text())
            cfg["gates"] = {"build": {"run": cmd, "mode": "block"}}
            Path(".team/config.json").write_text(json.dumps(cfg))

        # a missing command is a setup problem: blocked for a human, not counted as a failed attempt
        gate("no-such-command-xyz")
        out = run("finish", "build", "APP-1", ok=False)
        assert "BLOCKED: APP-1" in out and "command not found" in out
        assert status(chore) == "in-progress" and "blocked: true" in chore.read_text()
        assert run("queue").strip() == "queue is empty" and "gate failed" not in chore.read_text()

        # a failing test is still a normal gate failure
        gate("echo '1 test failed'; exit 1")
        out = run("finish", "build", "APP-1", ok=False)
        assert "FAIL: APP-1" in out and "setup problem" not in out

        # a flaky simulator launch is retried once
        gate("if [ -f .git/once ]; then exit 0; fi; touch .git/once; echo 'Failed to launch app on simulator'; exit 65")
        out = run("finish", "build", "APP-1")
        assert "RETRY" in out and "PASS: APP-1 → done" in out

        # a ticket blocked in build doesn't hold the one-at-a-time slot (found in the in-app test)
        sh("git checkout -q main")
        stuck = Path(run("new", "chore", "Stuck").strip())
        run("queue", "add", "APP-2")
        run("start", "build", "APP-2")
        fill(stuck, "Implementation notes", "x")
        sh("git commit -q --allow-empty -m 'APP-2 x'")
        gate("no-such-command-xyz")
        run("finish", "build", "APP-2", ok=False)
        assert status(stuck) == "in-progress" and "blocked: true" in stuck.read_text()
        run("new", "chore", "Next one")
        run("queue", "add", "APP-3")
        assert run("next").strip() == "NEXT: build APP-3"
        run("start", "build", "APP-3")


def check_guard():
    import os
    guard = TEAM.parent / "guard.py"

    def edit(path, cwd):
        r = subprocess.run([sys.executable, str(guard)], input=json.dumps(
            {"tool_name": "Edit", "cwd": str(cwd), "tool_input": {"file_path": str(path)}}),
            capture_output=True, text=True)
        return r.returncode, r.stdout + r.stderr

    with tempfile.TemporaryDirectory() as d:
        os.chdir(d)
        sh("git init -q -b main && git config user.email t@t && git config user.name t "
           "&& git commit -q --allow-empty -m init")
        assert edit("app.py", d) == (0, "")  # not a sprintkit project yet: silent
        run("init", "--prefix", "APP")
        chore = Path(run("new", "chore", "Bump").strip())
        assert edit(chore, d) == (0, "")  # tickets are always editable
        code, out = edit("src/app.py", d)
        assert code == 0 and "additionalContext" in out and "src/app.py" in out  # default: warn
        cfg = json.loads(Path(".team/config.json").read_text())
        Path(".team/config.json").write_text(json.dumps({**cfg, "guard": "block"}))
        code, out = edit(Path(d, "src/app.py"), "/")
        assert code == 2 and "no ticket" in out
        run("start", "build", "APP-1")
        assert edit("src/app.py", d) == (0, "")  # a ticket is being built
        Path(".team/config.json").write_text(json.dumps({**cfg, "guard": "off"}))
        sh("git checkout -q main")
        chore.write_text(chore.read_text().replace("status: in-progress", "status: done"))
        assert edit("src/app.py", d) == (0, "")


def check_release():
    import os
    with tempfile.TemporaryDirectory() as d:
        os.chdir(d)
        sh("git init -q -b main && git config user.email t@t && git config user.name t "
           "&& git commit -q --allow-empty -m init")
        run("init", "--prefix", "APP")
        git = lambda *a: subprocess.check_output(["git", *a], text=True).strip()
        assert "no done tickets" in run("sanity", ok=False)
        paths = [Path(run("new", kind, title).strip()) for kind, title in
                 (("story", "Dark mode"), ("bug", "Crash on save"), ("spike", "Pick a DB"), ("chore", "Unfinished"))]
        for t in paths[:3]:
            t.write_text(t.read_text().replace("status: backlog", "status: done"))

        def gates(**g):
            cfg = json.loads(Path(".team/config.json").read_text())
            cfg["gates"] = {k: {"run": v, "mode": "block"} for k, v in g.items()}
            Path(".team/config.json").write_text(json.dumps(cfg))

        # sanity fails: nothing changes, a bug is offered
        gates(sanity="echo smoke broke; exit 1")
        out = run("sanity", ok=False)
        assert "smoke broke" in out and "OFFER" in out and status(paths[0]) == "done"
        # sanity passes: story + bug become candidates, the spike stays done, a story means a minor version
        gates(sanity="test \"$RELEASE_VERSION\" = v0.1.0", deploy="echo deployed > .git/deployed")
        assert "PASS: v0.1.0" in run("sanity")
        assert [status(t) for t in paths] == ["release-candidate", "release-candidate", "done", "backlog"]
        assert "waiting for deploy" in run("sanity", ok=False)
        assert "no release is deploying" in run("deploy", "finish", ok=False)

        # deploy: the changelog must be committed, else back to candidate and nothing tagged
        out = run("deploy", "start")
        assert "RELEASE: v0.1.0" in out and "APP-1 story: Dark mode" in out and "APP-3" not in out
        assert "no entry for v0.1.0" in run("deploy", "finish", ok=False)
        assert git("tag") == ""
        run("deploy", "start")
        Path("CHANGELOG.md").write_text("# Changelog\n\n## v0.1.0\n- Dark mode (APP-1)\n")
        sh("git add CHANGELOG.md && git commit -q -m 'Release v0.1.0: changelog'")
        gates(deploy="exit 4")
        assert "exited 4" in run("deploy", "finish", ok=False) and git("tag") == ""
        gates(deploy="echo deployed > .git/deployed")
        run("deploy", "start")
        assert "PASS: released v0.1.0" in run("deploy", "finish")
        assert git("tag") == "v0.1.0" and Path(".git/deployed").exists()
        assert [status(t) for t in paths] == ["released", "released", "done", "backlog"]

        # retro: numbers from the Logs, the file must hold a process change (SK-8)
        story = paths[0]
        story.write_text(story.read_text().replace("## Log\n", "## Log\n- 2026-10-01T10:00 refined → in-progress (build)\n"
            "- 2026-10-01T11:00 review gate failed → refined: reviewer asked for changes\n- 2026-10-01T13:30 testing → done\n"))
        out = run("retro", "start")
        assert "RELEASE: v0.1.0" in out and "| APP-1 Dark mode | story | 1 | 1 | 0 | 0 | 3.5 |" in out
        assert "APP-3" not in out  # the spike wasn't released
        assert "doesn't exist" in run("retro", "finish", ok=False)
        Path(".team/retros/v0.1.0.md").write_text("# Retro v0.1.0\n\n## Went well\n- all\n")
        assert "Process change" in run("retro", "finish", ok=False)
        Path(".team/retros/v0.1.0.md").write_text("# Retro v0.1.0\n\n## Process change\nAdd a blocking build gate.\n")
        assert "PASS" in run("retro", "finish")
        assert "isn't released" in run("retro", "start", "v9.9.9", ok=False)

        # bugs and chores only → patch version; no sanity command → warned, not silently "checked"
        gates()
        paths[3].write_text(paths[3].read_text().replace("status: backlog", "status: done"))
        out = run("sanity")
        assert "PASS: v0.1.1" in out and "WARN: no sanity command" in out


def check_setup():
    import os
    import urllib.request
    with tempfile.TemporaryDirectory() as home, tempfile.TemporaryDirectory() as tmp:
        proj = str(Path(tmp, "shopapp"))  # fixed name: random temp names like tmpa_b4 change the prefix
        os.mkdir(proj)
        # fake ~/.claude with one installed plugin that has an agent and a skill
        plug = Path(home, "cache/acme")
        (plug / "agents").mkdir(parents=True)
        (plug / "agents/fixer.md").write_text("---\nname: fixer\ndescription: Fixes things\n---\n")
        (plug / "skills/tdd").mkdir(parents=True)
        (plug / "skills/tdd/SKILL.md").write_text("---\nname: tdd\ndescription: |\n  multi\n---\n")
        Path(home, ".claude/plugins").mkdir(parents=True)
        Path(home, ".claude/plugins/installed_plugins.json").write_text(json.dumps(
            {"version": 2, "plugins": {"acme@market": [{"installPath": str(plug)}]}}))
        Path(home, ".claude/settings.json").write_text(json.dumps({"enabledPlugins": {"acme@market": True}}))
        Path(proj, "package.json").write_text(json.dumps({"scripts": {"test": "jest"}}))
        Path(proj, "Package.swift").write_text("// swift-tools-version:5.9\n")
        Path(proj, ".claude").mkdir()
        Path(proj, ".claude/settings.json").write_text(json.dumps({"permissions": {"allow": ["Bash(ls)"]}}))

        env = {**os.environ, "HOME": home, "GIT_AUTHOR_NAME": "t", "GIT_AUTHOR_EMAIL": "t@t",
               "GIT_COMMITTER_NAME": "t", "GIT_COMMITTER_EMAIL": "t@t"}
        srv = subprocess.Popen([sys.executable, str(TEAM), "serve", "--port", "0"], cwd=proj, env=env,
                               stdout=subprocess.PIPE, text=True)
        try:
            base = srv.stdout.readline().split()[-1]

            def post(data):
                r = urllib.request.Request(base + "/api/setup", data=json.dumps(data).encode(),
                                           headers={"Content-Type": "application/json"})
                try:
                    with urllib.request.urlopen(r) as resp:
                        return resp.status, json.loads(resp.read())
                except urllib.error.HTTPError as e:
                    return e.code, json.loads(e.read())

            assert b"Set up sprintkit" in urllib.request.urlopen(base + "/").read()
            info = json.loads(urllib.request.urlopen(base + "/api/setup").read())
            acme = info["plugins"][0]
            assert acme["id"] == "acme@market" and acme["enabled"]
            assert acme["agents"][0]["id"] == "acme:fixer" and acme["skills"][0] == {"id": "acme:tdd", "description": ""}
            assert {"run": "npm test", "why": "package.json test script"} in info["checks"]
            assert {"run": "swift test", "why": "Swift package (Package.swift)"} in info["checks"]
            assert not info["git"]["isRepo"] and info["prefix"] == "SHOP"

            # validation happens before anything is touched
            assert post({"prefix": "bad prefix"})[0] == 400
            assert post({"prefix": "AB", "github": {"mode": "create", "name": "x; rm -rf ~", "visibility": "private"}})[0] == 400
            assert post({"prefix": "AB", "stages": {"build": {"agent": "a b"}}})[0] == 400
            assert not Path(proj, ".git").exists()

            code, res = post({"prefix": "AB", "stages": {"refine": {"human": True}, "build": {"agent": "acme:fixer"}},
                              "context": [], "gates": {"build": {"run": "npm test", "mode": "block"}},
                              "plugins": {"acme@market": False},
                              "github": {"mode": "link", "url": "https://github.com/me/proj"}})
            assert code == 200 and all(s["ok"] for s in res["steps"]), res
            cfg = json.loads(Path(proj, ".team/config.json").read_text())
            assert cfg["stages"]["build"] == {"agent": "acme:fixer"} and cfg["gates"]["build"]["mode"] == "block"
            settings = json.loads(Path(proj, ".claude/settings.json").read_text())
            assert settings == {"permissions": {"allow": ["Bash(ls)"]}, "enabledPlugins": {"acme@market": False}}
            git = lambda *a: subprocess.check_output(["git", *a], cwd=proj, text=True).strip()
            assert git("remote", "get-url", "origin") == "https://github.com/me/proj"
            assert git("log", "--oneline").endswith("Initial commit")
            assert ".team/" in Path(proj, ".gitignore").read_text().splitlines()  # SK-13
            assert not git("status", "--porcelain", "--", ".gitignore")  # committed, so build gates don't trip on it

            # after setup: the board is served, and setup can't run twice
            assert b"sprintkit board" in urllib.request.urlopen(base + "/").read()
            assert post({"prefix": "AB"})[0] == 409

            # settings: edits what the screen shows, keeps hand-written config
            assert b"Set up sprintkit" in urllib.request.urlopen(base + "/settings").read()  # same page, settings mode
            cfg_path = Path(proj, ".team/config.json")
            cfg = json.loads(cfg_path.read_text())
            cfg.update({"flows": {"bug": ["build"]}, "context_max_chars": 900, "context": ["no-such-tool-xyz ."],
                        "gates": {**cfg["gates"], "qa": {"run": "make e2e", "mode": "block"}},
                        "stages": {**cfg["stages"], "qa": {"command": "./qa.sh"}}})
            cfg_path.write_text(json.dumps(cfg))
            info = json.loads(urllib.request.urlopen(base + "/api/setup").read())
            assert info["config"]["flows"] == {"bug": ["build"]}
            assert info["contextMissing"] == ["no-such-tool-xyz ."]  # flagged in Settings

            def save(data):
                r = urllib.request.Request(base + "/api/settings", data=json.dumps(data).encode(),
                                           headers={"Content-Type": "application/json"})
                try:
                    with urllib.request.urlopen(r) as resp:
                        return resp.status, json.loads(resp.read())
                except urllib.error.HTTPError as e:
                    return e.code, json.loads(e.read())

            code, res = save({"stages": {"refine": {"agent": "acme:fixer", "skills": ["acme:tdd"]},
                                         "build": {"human": True}, "qa": {"command": "./qa.sh"}},
                              "context": ['rg -l "$TICKET_TITLE"'], "gates": {},
                              "plugins": {"acme@market": True}, "autopilot": {"max_attempts": 3},
                              "github": {"mode": "keep"}})
            assert code == 200 and all(s["ok"] for s in res["steps"]), res
            cfg = json.loads(cfg_path.read_text())
            assert cfg["prefix"] == "AB" and cfg["flows"] == {"bug": ["build"]} and cfg["context_max_chars"] == 900
            assert cfg["gates"] == {"qa": {"run": "make e2e", "mode": "block"}}  # build gate off, qa kept
            assert cfg["stages"]["qa"] == {"command": "./qa.sh"} and cfg["stages"]["build"] == {"human": True}
            assert cfg["stages"]["refine"] == {"agent": "acme:fixer", "skills": ["acme:tdd"]}
            assert cfg["autopilot"]["max_attempts"] == 3 and cfg["context"] == ['rg -l "$TICKET_TITLE"']
            assert json.loads(Path(proj, ".claude/settings.json").read_text())["enabledPlugins"] == {"acme@market": True}
            assert save({"stages": {"build": {"agent": "x; rm"}}})[0] == 400
            assert save({"autopilot": {"max_attempts": 99}})[0] == 400
            assert json.loads(cfg_path.read_text())["autopilot"]["max_attempts"] == 3  # rejected saves change nothing
        finally:
            srv.terminate()


def main():
    with tempfile.TemporaryDirectory() as d:
        import os
        os.chdir(d)
        sh("git init -q -b main && git config user.email t@t && git config user.name t "
           "&& git commit -q --allow-empty -m init")
        run("init", "--prefix", "APP")

        # story: refine fails without outputs, goes back to backlog
        story = Path(run("new", "story", "Login form").strip())
        run("start", "refine", "APP-1")
        assert status(story) == "refining"
        out = run("finish", "refine", "APP-1", ok=False)
        assert "Acceptance criteria" in out and status(story) == "backlog"

        # build is refused before refine (story flow)
        run("start", "build", "APP-1", ok=False)

        # refine passes once tech-lead outputs exist
        run("start", "refine", "APP-1")
        fill(story, "Acceptance criteria", "- [ ] user can log in")
        fill(story, "Technical notes", "Use the existing session middleware.")
        story.write_text(story.read_text().replace("blocked: false", "blocked: false\npoints: 3"))
        run("finish", "refine", "APP-1")
        assert status(story) == "refined"

        # build: branch created, gate fails without a commit
        out = run("start", "build", "APP-1")
        assert "BRANCH: APP-1-login-form" in out
        assert "APP-1-login-form" in subprocess.check_output(["git", "branch", "--show-current"], text=True)
        fill(story, "Implementation notes", "Added form.")
        assert "no commit" in run("finish", "build", "APP-1", ok=False)
        assert status(story) == "in-progress"

        # one ticket in progress at a time
        run("new", "bug", "Crash on save")
        assert "already in-progress" in run("start", "build", "APP-2", ok=False)

        # a commit for APP-12 must not satisfy APP-1
        Path("login.txt").write_text("form")
        sh("git add login.txt && git commit -q -m 'APP-12 unrelated'")
        assert "no commit" in run("finish", "build", "APP-1", ok=False)

        # user gate in warn mode advances, in block mode doesn't
        sh("git commit -q --allow-empty -m 'APP-1 login form'")
        cfg = json.loads(Path(".team/config.json").read_text())
        cfg["gates"] = {"build": {"run": "exit 3"}}
        Path(".team/config.json").write_text(json.dumps(cfg))
        out = run("finish", "build", "APP-1")
        assert "WARN" in out and status(story) == "in-review"

        # bug flow skips refine; blocking gate keeps it in progress
        sh("git checkout -q main")
        cfg["gates"]["build"]["mode"] = "block"
        Path(".team/config.json").write_text(json.dumps(cfg))
        run("start", "refine", "APP-2", ok=False)
        run("start", "build", "APP-2")
        bug = next(Path(".team/tickets").glob("APP-2-*.md"))
        fill(bug, "Implementation notes", "Fixed.")
        sh("git commit -q --allow-empty -m 'APP-2 fix crash'")
        assert "exited 3" in run("finish", "build", "APP-2", ok=False)
        assert status(bug) == "in-progress"

        # context providers get ticket data as env vars, not interpolation
        cfg["context"] = ['printf "%s" "$TICKET_TITLE"']
        Path(".team/config.json").write_text(json.dumps(cfg))
        run("new", "chore", '"; touch pwned; echo "')
        sh("git checkout -q main")
        bug.write_text(bug.read_text().replace("status: in-progress", "status: in-review"))
        run("start", "build", "APP-3")
        assert not Path("pwned").exists()

        board = run("board")
        assert "IN-REVIEW (2)" in board and "IN-PROGRESS (1)" in board
        check_server()
        for n in range(5, 11):
            run("new", "chore", f"Filler {n}")
        board = run("board")
        assert board.index("APP-9 ") < board.index("APP-10 ")  # ID order, not alphabetical
    check_autopilot()
    check_review()
    check_qa()
    check_gate_setup()
    check_guard()
    check_release()
    check_setup()
    print("all checks passed")


if __name__ == "__main__":
    main()
