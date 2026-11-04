#!/bin/sh
# Session-start note for pstack: which adapter to read, and when to route a task to poteto-mode.
# The plugin's hooks file passes the runtime name. Set JUM_PSTACK_ROUTING=off to silence it.
set -eu

[ "${JUM_PSTACK_ROUTING:-on}" = off ] && exit 0

root="${CLAUDE_PLUGIN_ROOT:-}"
[ -n "$root" ] || root="$(cd "$(dirname "$0")/.." && pwd)"

case "${1:-}" in
  claude)
    runtime="Claude Code"
    adapter="claude-code.md"
    invoke="/pstack:poteto-mode"
    sheet=""
    ;;
  codex)
    runtime="Codex"
    adapter="codex.md"
    invoke="\$pstack:poteto-mode"
    sheet="${CODEX_HOME:-${HOME:-}/.codex}/pstack-models.md"
    ;;
  *)
    echo "session-start.sh: expected claude or codex, got '${1:-}'" >&2
    exit 2
    ;;
esac

cat <<EOF
<pstack>
You have pstack (jum-pstack build). This session runs in $runtime. pstack skills use Cursor names, so read $root/docs/harness/$adapter once per session before you follow one.

Follow the poteto-mode skill ($root/skills/poteto-mode/SKILL.md, which the user types as $invoke) when a task:
- touches more than one file, or changes a signature that other files call
- involves a design or architecture choice
- is a bug whose cause is not known yet, or a performance issue

Work directly on smaller tasks, such as a contained one-file change with an obvious check, a question, or a one-line edit, and verify on the real artifact. User instructions (CLAUDE.md, AGENTS.md, direct requests) take precedence over this note.
</pstack>
EOF

if [ -n "$sheet" ] && [ -r "$sheet" ]; then
  printf '\n<pstack-models file="%s">\n' "$sheet"
  cat "$sheet"
  printf '</pstack-models>\n'
fi
