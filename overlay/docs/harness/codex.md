# pstack in Codex

pstack skills use Cursor names. In Codex, read this file once per session, then map each Cursor name in a skill with the tables below. `<pstack>` means the installed plugin folder that holds `skills/`, `agents/`, and `docs/`. If a Cursor field has no row, drop it and say so. Never pass a field or value the tool schema rejects.

## Tools

| Cursor | Codex |
| --- | --- |
| `Task` | `spawn_agent`, then `wait_agent` for its result, then `close_agent` when the session offers it. Run parallel work as several `spawn_agent` calls in one turn. Subagents need `multi_agent` on (`[features]` `multi_agent = true` in `~/.codex/config.toml`). Without it, do the work yourself in sequence and say so. A required independent review never degrades: it stays blocked. |
| `AskQuestion` | Ask in plain text and wait for the answer. |
| Open a todolist | `update_plan`. |
| Run another pstack skill (`/name` or "the **name** skill") | Read `<pstack>/skills/<name>/SKILL.md` and follow it. When you tell the user to type it, write `$pstack:<name>`. |
| `Grep`, `Glob` | `rg` and `find` through the shell. |

## Subagent fields

| Cursor | Codex |
| --- | --- |
| `subagent_type: generalPurpose` | A plain `spawn_agent`. |
| `poteto-agent`, `comment-sicko` | Codex has no custom agent types. Spawn a plain agent whose brief starts with "Read `<pstack>/agents/<name>.md` in full and follow it." |
| `readonly: true` | Put "do not edit files" in the brief, and check `git status` afterward. |
| `readonly: false` | A plain `spawn_agent`. |
| `environment: "cloud"` | Have the worker create its own worktree with `git worktree add` on the branch or commit you name. |
| `environment: "local"` | Omit. |
| `cloud_base_branch: <b>` | Tell the worker to check out `<b>` first. |
| `run_in_background: true` | Omit. `spawn_agent` already runs alongside your turn. |
| `resume` | Spawn a new agent and paste the earlier result into its brief. |
| `file_attachments` | List the paths in the brief. |

## Models

| Cursor | Codex |
| --- | --- |
| `claude-<family>-<version>-<effort>[-fast]`, such as `claude-opus-5-5-xhigh` | Claude models do not run in Codex. Use the role's line in the model sheet. Without one, pass no `model` so the agent runs on the session model, and say so. |
| A `grok-*`, `gpt-*`, or other non-Claude slug | Pass it as `model` only when the session offers that model. Otherwise pass no `model` and say so. |
| `auto` or `inherit-parent` | Pass no `model`. |
| The `pstack-models.mdc` rule, `~/.cursor/rules/pstack-models.mdc` | `~/.codex/pstack-models.md` (`$CODEX_HOME/pstack-models.md`). The jum-pstack session-start hook prints it into each session when it exists. If the file or the role's line is missing, use the skill's default and say which model ran. |
| A role value `<model> <effort>`, such as `opus high` | `model` and `reasoning_effort` on `spawn_agent`, when the session offers that model. A panel role wants distinct models; if only one is available, vary `reasoning_effort` and say that diversity was reduced. |

## setup-pstack

Codex has no always-applied rules folder, so `setup-pstack` writes its sheet to `~/.codex/pstack-models.md`. Follow its steps with these changes:

- Detect. The detected models are the `model` values `spawn_agent` accepts in this session. If you cannot tell, ask the user which Codex models they use.
- Write. Write `~/.codex/pstack-models.md` with no frontmatter, then the comment lines, the `# budget` line, and one line per role. Overwrite the whole file. Never put the role lines in `AGENTS.md`.

## Paths

| Cursor | Codex |
| --- | --- |
| `.cursor/skills/`, `~/.cursor/skills/` | `.agents/skills/`, `~/.agents/skills/` |
| `~/.cursor/plugins/`, `.cursor-plugin/plugin.json` | `~/.codex/plugins/`, `.codex-plugin/plugin.json` |
| `.cursor/rules/*.mdc`, always-applied rules | `AGENTS.md` in the project, or `~/.codex/AGENTS.md` for every project. Codex never reads `.mdc` files. The model sheet is the exception. See Models. |
| `https://github.com/cursor/plugins/blob/main/pstack/<path>` | `<pstack>/<path>` when that file exists. Read the local copy and never fetch it. Give the user the URL when they need a link. |
| Transcripts in `~/.cursor/projects/<slug>/agent-transcripts/` | `~/.codex/sessions/YYYY/MM/DD/rollout-*.jsonl` (`$CODEX_HOME/sessions`). Read only sessions whose working directory is this workspace. |

## Cursor-only features

When a step needs one of these, put one line in your reply, `Skipped in Codex: <step>. <reason>.`, then go on to the next step. Do not stop, ask, or retry. When a later step needs what the skipped step made, leave a placeholder and name it in the line.

| Cursor | Codex |
| --- | --- |
| Cursor Automations: routines, `update_state` routine calls, `api2.cursor.sh/automations` webhooks, routine wakes, and `SendToUser` secret requests | Skip with the line. Say that a Codex app scheduled task can run a recurring prompt instead. |
| Bugbot | Bugbot comments on a GitHub PR are ordinary review threads, so triage them with the forge command the step gives. Skip a step that starts, waits for, or configures Bugbot when the PR has no Bugbot check or comment. |
| Cursor cloud agents | `environment: "cloud"` maps to a worktree, as in Subagent fields. Skip a step that needs the cloud agent itself, such as its dashboard or its own machine. |
| A built-in PR tool | Use the forge command the step gives, such as `gh pr create`. That is not a skip, so write no line. |

## Waking and loops

Skills name Cursor's `/loop`. Codex has no `/loop`.

| Cursor | Codex |
| --- | --- |
| `/loop until <condition>`, the Autonomous run playbook | Set the finish condition as a goal with `/goal <condition>`. Codex keeps working until the goal is met, paused, or blocked. If `/goal` is missing, the user can turn it on with `codex features enable goals`. |
| `/loop 1h`, an audit tick | A Codex app scheduled task that returns to this chat. Without the app, tell the user the tick is not armed and what to re-run. Never claim a tick is armed when it is not. |
| A watcher subagent that wakes you on an event | `spawn_agent` the watcher, for example on `gh pr checks <n> --watch`, and `wait_agent` on it. |
