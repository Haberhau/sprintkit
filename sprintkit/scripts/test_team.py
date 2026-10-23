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
    print("all checks passed")


if __name__ == "__main__":
    main()
