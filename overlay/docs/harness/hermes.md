# pstack in Hermes

pstack skills use Cursor names. In Hermes, read this file once per session, then map each Cursor name in a skill with the tables below. `<pstack>` means the folder that holds `skills/`, `agents/`, and `docs/`: `plugins/pstack` in the jum-pstack clone that `skills.external_dirs` points at. If a Cursor field has no row, drop it and say so. Never pass a field or value the tool schema rejects.

## Tools

| Cursor | Hermes |
| --- | --- |
| `Task` | `delegate_task` with a `goal` and a full `context`. The child starts with a fresh conversation and sees nothing else. Run parallel work as one call with a `tasks` array (ten at a time by default). |
| `AskQuestion` | `clarify`. |
| Open a todolist, or copy steps into the todolist tool | `todo`, with one item per step. |
| Run another pstack skill (`/name` or "the **name** skill") | `skill_view` the skill and follow it, or read `<pstack>/skills/<name>/SKILL.md`. When you tell the user to type it, write `/<name>`. |
| `Grep`, `Glob` | `search_files`, or `rg` and `find` through `terminal`. |

## Subagent fields

| Cursor | Hermes |
| --- | --- |
| `subagent_type: generalPurpose` | A plain `delegate_task`. |
| `poteto-agent`, `comment-sicko` | Hermes has no custom agent types. Start the child's `context` with "Read `<pstack>/agents/<name>.md` in full and follow it." |
| The `model:` line in `poteto-agent`'s file | It holds a Cursor slug, and the child only reads the file as text, so the line sets no model. Pick the model with the Models table, as for any other `delegate_task`, and say which model ran. |
| `readonly: true` | Say "do not edit files" in the goal, and check `git status` afterward. Children inherit your toolsets, so this is a brief, not a sandbox. |
| `readonly: false` | A plain `delegate_task`. |
| `environment: "cloud"` | Name a git worktree in the `context` and have the child create it with `git worktree add` and work only there. |
| `environment: "local"` | Omit. |
| `cloud_base_branch: <b>` | Tell the child to check out `<b>` first. |
| `run_in_background: true` | Omit. A `tasks` batch already runs in the background and reports when its tasks finish. End your turn instead of polling. |
| `resume` | Start a new `delegate_task` and paste the earlier result into its `context`. |
| `file_attachments` | List the paths in `context`. |

## Models

| Cursor | Hermes |
| --- | --- |
| `claude-<family>-<version>-<effort>[-fast]`, such as `claude-opus-5-5-xhigh` | `delegate_task` takes no model. With the default backend every child runs on `delegation.model`, or on your model when that is unset. With the `advanced-delegation` plugin's `model_map` backend, pick the option that matches the role. Otherwise say which model ran. |
| A `gemini-*` or other non-Claude slug | The same as above: a `model_map` option when one matches, otherwise say which model ran. |
| `auto` or `inherit-parent` | The default backend. |
| The `pstack-models.mdc` rule, `~/.cursor/rules/pstack-models.mdc` | `~/.hermes/pstack-models.md`. Read it at the start of a pstack run. If the file or the role's line is missing, use the skill's default and say which model ran. |
| A role value `<model> <effort>`, such as `opus high` | The `model_map` option for that model. If the option cannot carry the effort, say so. A panel role wants distinct models; with one model, say that diversity was reduced. |

## setup-pstack

Hermes loads no rules folder, so `setup-pstack` writes its sheet to `~/.hermes/pstack-models.md`. Follow its steps with these changes:

- Detect. Read `delegation` in `~/.hermes/config.yaml`: `delegation.model`, or `delegation.backends.model_map.options` when that backend is on. Never edit `config.yaml` without asking.
- Write. Write `~/.hermes/pstack-models.md` with no frontmatter, then the comment lines, the `# budget` line, and one line per role. Overwrite the whole file.

## Paths

| Cursor | Hermes |
| --- | --- |
| `.cursor/skills/`, `~/.cursor/skills/` | `.agents/skills/` in the project, and `~/.hermes/skills/` |
| `~/.cursor/plugins/`, `.cursor-plugin/plugin.json` | Hermes has no plugin manifest for pstack. It loads the skills through `skills.external_dirs` in `~/.hermes/config.yaml`. |
| `.cursor/rules/*.mdc`, always-applied rules | `.hermes.md` or `AGENTS.md` in the project, or `SOUL.md` in the Hermes home for every project. Hermes never reads `.mdc` files. |
| `https://github.com/cursor/plugins/blob/main/pstack/<path>` | `<pstack>/<path>` when that file exists. Read the local copy and never fetch it. Give the user the URL when they need a link. |
| Transcripts in `~/.cursor/projects/<slug>/agent-transcripts/` | `session_search`. |

## Cursor-only features

When a step needs one of these, put one line in your reply, `Skipped in Hermes: <step>. <reason>.`, then go on to the next step. Do not stop, ask, or retry. When a later step needs what the skipped step made, leave a placeholder and name it in the line.

| Cursor | Hermes |
| --- | --- |
| Cursor Automations: routines, `update_state` routine calls, `api2.cursor.sh/automations` webhooks, routine wakes, and `SendToUser` secret requests | Skip with the line. Say that a Hermes cron job (`cronjob_manage`) can run a recurring prompt instead. |
| Bugbot | Bugbot comments on a GitHub PR are ordinary review threads, so triage them with the forge command the step gives. Skip a step that starts, waits for, or configures Bugbot when the PR has no Bugbot check or comment. |
| Cursor cloud agents | `environment: "cloud"` maps to a worktree, as in Subagent fields. Skip a step that needs the cloud agent itself, such as its dashboard or its own machine. |
| A built-in PR tool | Use the forge command the step gives, such as `gh pr create`. That is not a skip, so write no line. |

## Waking and loops

Skills name Cursor's `/loop`. Hermes has no `/loop`.

| Cursor | Hermes |
| --- | --- |
| `/loop until <condition>`, the Autonomous run playbook | Keep working in this session until the condition holds. For a run that must outlive the session, ask before creating a `cronjob_manage` job whose prompt resumes from the Pause safely note and re-checks the condition. |
| `/loop 1h`, an audit tick | A `cronjob_manage` job every hour, created only with the user's go. Each run starts fresh, so its prompt reads the checkpoint first. Never claim a tick is armed when it is not. |
| A watcher subagent that wakes you on an event | `delegate_task` the watcher. Its result arrives between your turns, so end your turn instead of polling. |
