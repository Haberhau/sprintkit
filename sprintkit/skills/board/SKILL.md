---
name: board
description: Open the live sprintkit board in the browser - tickets move as stages run, new tickets can be created there. Use "text" as argument for a terminal view.
argument-hint: "[text]"
allowed-tools: Bash(python3 ${CLAUDE_PLUGIN_ROOT}/scripts/team.py *)
---

If the argument is `text`: run `python3 "${CLAUDE_PLUGIN_ROOT}/scripts/team.py" board` and show the output as-is in a code block. Stop.

Otherwise:
1. Run `python3 "${CLAUDE_PLUGIN_ROOT}/scripts/team.py" serve` from the project root **in the background** (it keeps running). It prints the board URL, or says the port is in use when a board is already running. Then the URL it names is the board.
2. Open the URL in a browser pane if you have one; otherwise give the user the URL.
3. Tell the user in one or two lines: cards move on their own as stages run; "New ticket" creates tickets; the ▶ button on a card copies the next command (e.g. `/sprintkit:build APP-3`) to paste here. Cards can't be dragged between stages: they only move when a stage passes its gate.
