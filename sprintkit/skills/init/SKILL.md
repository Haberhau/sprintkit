---
name: init
description: Set up sprintkit for a project. Picks or creates the project folder, then opens a setup screen for GitHub, which agents and skills run each stage, which plugins this project uses, and quality checks.
argument-hint: "[new <project name>]"
allowed-tools: Bash(python3 ${CLAUDE_PLUGIN_ROOT}/scripts/team.py *)
---

## 1. The folder (your part: a browser can't pick folders)

- **New project** (the argument starts with `new`, or the user says so): ask where it should live if they haven't said (suggest a projects folder they already use). Create the folder. If your environment lets you move this session into it, do; otherwise tell the user to open Claude Code in that folder and run `/sprintkit:init` again, then stop.
- **Existing project**: use the current folder. If it's the home directory or clearly not a project, ask which folder first.
- If `.team/config.json` already exists, the project is set up: say so, offer `/sprintkit:board`, and stop.

## 2. The setup screen

1. From the project root, run `python3 "${CLAUDE_PLUGIN_ROOT}/scripts/team.py" serve` **in the background**. It prints its URL. If it says the port is in use, that may be another project's board: run it again with `--port 0` (picks a free port) and use the URL it prints.
2. Open the URL in a browser pane if you have one; otherwise give the user the URL.
3. Tell the user in two lines: the setup screen walks through GitHub, who runs each stage, which plugins are on for this project, and checks; when they press "Create project", the same page becomes the board.

## If there's no browser at all

Fall back to `python3 "${CLAUDE_PLUGIN_ROOT}/scripts/team.py" init --prefix <PREFIX>`, ask the user which agent should run refine and build, and edit `.team/config.json` accordingly.
