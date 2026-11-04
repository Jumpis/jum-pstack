---
name: pstack-router
description: Hermes only. Points pstack runs at the Hermes adapter and routes rigorous engineering tasks to poteto-mode. Loaded every session through skills.auto_load.
version: 1.0.0
metadata:
  hermes:
    tags: [pstack, workflow]
---

# pstack in this Hermes session

You have pstack from a jum-pstack clone. Its skills use Cursor names, so read the Hermes adapter once per session before you follow one. This skill sits at `hermes/skills/pstack-router/SKILL.md` in the clone, and the adapter is `plugins/pstack/docs/harness/hermes.md` in the same clone.

Follow the poteto-mode skill (`skill_view` poteto-mode) when a task:

- touches more than one file, or changes a signature that other files call
- involves a design or architecture choice
- is a bug whose cause is not known yet, or a performance issue

Work directly on smaller tasks, such as a contained one-file change with an obvious check, a question, or a one-line edit, and verify on the real artifact. User instructions (`AGENTS.md`, `.hermes.md`, direct requests) take precedence over this skill.

When the user keeps a pstack model sheet, it is `~/.hermes/pstack-models.md`.
