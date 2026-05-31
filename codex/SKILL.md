---
name: codex
description: Use when you want a second opinion, are stuck on a problem, need an independent code review, or want to run a parallel investigation. Also use when the user explicitly says "codex" or asks you to get another perspective.
---

# Codex CLI — Second-Opinion Consultant

OpenAI's Codex CLI as an independent reviewer, investigator, or parallel worker.
Think of it as an Eastern European Linux neckbeard wizard consultant — brilliant
at everything, great for a second perspective, but not someone you outsource all
your work to.

**Full docs:** https://developers.openai.com/codex/cli/reference

## When to Use

- You're stuck and want a fresh perspective
- Independent code review or doc review
- Parallel investigation while you work on something else
- User asks for "codex", "second opinion", or "another perspective"
- Sanity-checking your own approach before committing

## When NOT to Use

- Simple tasks you can handle directly
- As a replacement for doing your own work
- For every minor question (it's a consultant, not a crutch)

## Modes

- **Full auto** (default): `codex exec --full-auto "instruction"` — can read and
  write files in the workspace. Use for most tasks.
- **Read-only**: `codex exec -s read-only "instruction"` — can only
  read. Use for code reviews, doc reviews, analysis.
- **Workspace write**: `codex exec -s workspace-write "instruction"` — can read
  and write files. Use for implementation tasks.

## Quick Reference

```bash
# Default (full-auto) — can make changes
codex exec --full-auto "fix the failing tests" 2>&1

# Read-only — reviews, analysis, second opinions
codex exec -s read-only "review src/ for security issues" 2>&1

# Pipe context in
echo "review this diff:" | cat - <(git diff) | codex exec -s read-only - 2>&1

# Use a specific model
codex exec --full-auto -m gpt-5.5 "your instruction" 2>&1

# Set reasoning effort (low, medium, high, xhigh) via inline config
codex exec --full-auto -c model_reasoning_effort=xhigh "hard problem" 2>&1

# Combine model + reasoning effort
codex exec --full-auto -m gpt-5.5 -c model_reasoning_effort=xhigh "your instruction" 2>&1

# Save output to file
codex exec --full-auto -o results.txt "analyze the architecture" 2>&1

# Work in a specific directory
codex exec --full-auto -C /path/to/project "refactor the module" 2>&1
```

## Integration Pattern

Run Codex in the background with `run_in_background: true` on the Bash tool,
then continue your own work. Check results when notified.

```bash
# Fire off Codex review while you keep working
codex exec -s read-only "Review docs/design/ for inconsistencies." < /dev/null 2>&1
```

**Always pass `< /dev/null`** when spawning codex in background mode — see
"Stdin Gotcha" below. Without it codex hangs at the "Reading additional input
from stdin..." banner and never makes a single API call.

## IMPORTANT: Stdin Gotcha

**Codex blocks on stdin until it sees EOF.** Two failure modes both produce
the same symptom — the codex process sits at 0% CPU forever after printing
"Reading additional input from stdin..." with no further output:

1. **Chained after another command via `&&` or `;`.** Heredocs/pipes from the
   prior command leave stdin in a half-open state.
2. **Spawned via the Bash tool's `run_in_background: true`** without an
   explicit stdin redirect. The background harness doesn't close stdin, so
   codex waits indefinitely.

**Fix in both cases: redirect stdin from `/dev/null`.**

```bash
# BAD — will hang:
git commit -m "$(cat <<'EOF'
message
EOF
)" && codex exec -s read-only "review" 2>&1

# BAD — will hang in background mode:
# Bash({ command: 'codex exec --full-auto "..." 2>&1', run_in_background: true })

# GOOD — explicit stdin redirect:
codex exec -s read-only "review" < /dev/null 2>&1

# GOOD — separate Bash calls + stdin redirect:
# Call 1: git commit
# Call 2: codex exec -s read-only "review" < /dev/null 2>&1
```

Always run `codex exec` as its own standalone Bash tool call AND pass
`< /dev/null` (or another concrete stdin source) regardless of whether it's
foreground or background.

## Output Buffering Pitfall

**Do not pipe codex through `tail`, `head`, `grep`, or any aggregator.**

```bash
# BAD — output won't appear until codex finishes; if codex hangs you can't tell
# whether it's working or stuck
codex exec --full-auto "long task" 2>&1 | tail -100

# GOOD — let output stream to stdout (foreground) or to the background log file
codex exec --full-auto "long task" < /dev/null 2>&1
```

For long runs use `run_in_background: true` and tail the output file the Bash
tool writes (`/tmp/.../<task-id>.output`) — that gives you intermediate
visibility without breaking codex's stdout pipe.

## Sandbox Limitations Codex Imposes

Codex's `--full-auto` sandbox restricts what the spawned process can do, even
inside the workspace. Two limits matter for typical use:

1. **No network access.** `pip install`, `uv sync`, `npm install`, `pre-commit
   install`, downloading model weights — all fail with "name resolution"
   errors. Pre-install dependencies in the parent session before dispatching
   codex.

2. **`.git/` may be read-only**, especially under `run_in_background: true`.
   Codex can edit files in the workspace but `git add` / `git commit` fails
   with `Read-only file system` on `.git/index.lock`.

   **Workaround:** brief codex to do file work and run tests but **NOT
   commit**. The parent session commits after verifying the result. Example
   prompt suffix:

   ```
   DO NOT git commit anything — the parent session will commit after
   verifying. Stop after tests pass. Brief summary at the end.
   ```

This applies to anything codex would normally need network or write-elevated
access for: package installs, OS package managers, host-bridge commands like
`mac` (OrbStack), pushing to remotes, or rewriting git history.

## When Briefing a Sandboxed Codex Sub-Agent

State explicitly which steps it should skip:

- "Do not run `uv sync` / `npm install` / `pre-commit install` — parent will."
- "Do not git commit — parent will commit after verifying."
- "Skip any verification step that requires the install (e.g., `npm run
  test` if npm install is skipped)."
- "Report what you did, what you skipped, and why."

This avoids codex spending tokens on attempts that will fail in its sandbox,
and gives the parent a clear handoff point.

## Common Uses

- **Code review:** `codex exec "review this PR diff for bugs" < <(git diff main)`
- **Doc review:** `codex exec "check docs/ for contradictions and stale references"`
- **Debug help:** `codex exec "why might this test be flaky?" < test_output.log`
- **Architecture:** `codex exec "suggest how to refactor this module" < src/module.py`
- **Research:** `codex exec "what are the tradeoffs of approach A vs B for X?"`
