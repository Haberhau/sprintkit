---
name: retro
description: Look back on a sprintkit release - process numbers from the ticket Logs, what bounced, and one concrete process change.
argument-hint: "[vX.Y.Z]"
allowed-tools: Bash(python3 ${CLAUDE_PLUGIN_ROOT}/scripts/team.py *), Bash(python3 "${CLAUDE_PLUGIN_ROOT}/scripts/team.py" *)
---

1. Run `python3 "${CLAUDE_PLUGIN_ROOT}/scripts/team.py" retro start $ARGUMENTS` (no argument: the latest release). If it errors, show the error and stop.

2. Read `EXECUTOR` from the output and hand the work over. The executor must produce: the retro file at `PATH`, ending with a `## Process change` section holding one concrete change. It must not edit tickets, config or code.
   - `{"agent": "X"}`: call the Agent tool with `subagent_type: X`. The prompt is the full output of step 1 plus "Write the retro for this release." If the executor also lists `"skills"`, tell the agent to use them.
   - `{"skill": "X"}`: invoke skill X with the retro path as its argument, and do the work it describes yourself, writing only the output above.
   - `{"command": "C"}`: run C with RELEASE_VERSION exported from step 1's output.
   - `{"human": true}`: tell the user to write the file at `PATH` and run `/sprintkit:retro` again, then stop if the file doesn't exist yet; otherwise go to step 3.
   - `{}` or missing: no executor is configured. Tell the user and stop.

3. Run `python3 "${CLAUDE_PLUGIN_ROOT}/scripts/team.py" retro finish $ARGUMENTS`.
   - PASS: show the proposed process change and ask whether to apply it (e.g. edit `.team/config.json`). Apply it only on a yes.
   - FAIL: list the problems and offer to run the retro again.
