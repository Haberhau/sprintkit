---
name: release
description: Release all done sprintkit tickets - sanity check on the base branch, changelog, deploy command, git tag.
argument-hint: "[vX.Y.Z]"
allowed-tools: Bash(python3 ${CLAUDE_PLUGIN_ROOT}/scripts/team.py *), Bash(python3 "${CLAUDE_PLUGIN_ROOT}/scripts/team.py" *)
---

1. Sanity. Run `python3 "${CLAUDE_PLUGIN_ROOT}/scripts/team.py" sanity` (add `--version $ARGUMENTS` if a version was given).
   - An error saying a release is already waiting for deploy: skip to step 2.
   - FAIL: show the failing output in short. Nothing changed. Offer to file a bug ticket with it (`/sprintkit:ticket bug …`), then stop.
   - PASS (and WARN lines, if no sanity command is configured): mention them and go on.

2. Run `python3 "${CLAUDE_PLUGIN_ROOT}/scripts/team.py" deploy start`. If it errors, show the error and stop.

3. Read `EXECUTOR` from the output and hand the work over. The executor must produce: a `CHANGELOG.md` entry for the version, committed on the base branch. It must not tag, push or deploy.
   - `{"agent": "X"}`: call the Agent tool with `subagent_type: X`. The prompt is the full output of step 2 plus "Write and commit the changelog for this release." If the executor also lists `"skills"`, tell the agent to use them.
     If the Agent tool says that agent type doesn't exist and X starts with `sprintkit:` (the plugin was installed or updated after this session started, so its agents aren't registered yet), call it with `subagent_type: general-purpose` instead, and put the full text of `${CLAUDE_PLUGIN_ROOT}/agents/<name after "sprintkit:">.md` (without its frontmatter) at the top of the prompt. Mention once that a new session would load the agents directly.
   - `{"skill": "X"}`: invoke skill X with the release path as its argument, and do the work it describes yourself, writing only the output above.
   - `{"command": "C"}`: run C with RELEASE_VERSION exported from step 2's output.
   - `{"human": true}`: if `RESUMED: no`, tell the user to write and commit the changelog entry and run `/sprintkit:release` again, then stop. If `RESUMED: yes`, go straight to step 4.
   - `{}` or missing: no executor is configured. Tell the user and stop.

4. Run `python3 "${CLAUDE_PLUGIN_ROOT}/scripts/team.py" deploy finish`.
   - PASS: the deploy command ran, the version is tagged and the tickets are released. Say so in one line, including the note about pushing the tag.
   - FAIL: list the problems. The release is a candidate again; nothing was tagged. Offer to run `/sprintkit:release` again once it's fixed.
   - WARN lines: mention them.
