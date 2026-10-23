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
        assert by_id["APP-1"]["status"] == "in-review" and by_id["APP-1"]["next"] == ""
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
        out = run("next")
        assert "DEQUEUED: APP-2" in out and out.strip().endswith("NEXT: none")

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


def check_setup():
    import os
    import urllib.request
    with tempfile.TemporaryDirectory() as home, tempfile.TemporaryDirectory() as proj:
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
            assert not info["git"]["isRepo"] and info["prefix"] == Path(proj).name[:4].upper()

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

            # after setup: the board is served, and setup can't run twice
            assert b"sprintkit board" in urllib.request.urlopen(base + "/").read()
            assert post({"prefix": "AB"})[0] == 409

            # settings: edits what the screen shows, keeps hand-written config
            assert b"Set up sprintkit" in urllib.request.urlopen(base + "/settings").read()  # same page, settings mode
            cfg_path = Path(proj, ".team/config.json")
            cfg = json.loads(cfg_path.read_text())
            cfg.update({"flows": {"bug": ["build"]}, "context_max_chars": 900,
                        "gates": {**cfg["gates"], "qa": {"run": "make e2e", "mode": "block"}},
                        "stages": {**cfg["stages"], "qa": {"command": "./qa.sh"}}})
            cfg_path.write_text(json.dumps(cfg))
            assert json.loads(urllib.request.urlopen(base + "/api/setup").read())["config"]["flows"] == {"bug": ["build"]}

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
    check_autopilot()
    check_setup()
    print("all checks passed")


if __name__ == "__main__":
    main()
