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

- **Workspace write** (default for tasks): `codex exec --sandbox workspace-write
  "instruction"` — can read and write files in the workspace. Use for most tasks.
- **Read-only**: `codex exec -s read-only "instruction"` — can only
  read. Use for code reviews, doc reviews, analysis.
- **Full auto**: `codex exec --full-auto "instruction"` — same as workspace-write
  + auto-approval, but `--full-auto` is now **DEPRECATED** (prints
  `warning: --full-auto is deprecated; use --sandbox workspace-write instead`).
  It still works — the warning is NOT a failure — but prefer
  `--sandbox workspace-write` in new invocations.

## Quick Reference

```bash
# Default (workspace-write) — can make changes
codex exec --sandbox workspace-write "fix the failing tests" 2>&1

# Read-only — reviews, analysis, second opinions
codex exec -s read-only "review src/ for security issues" 2>&1

# Pipe context in
echo "review this diff:" | cat - <(git diff) | codex exec -s read-only - 2>&1

# Use a specific model (see "Model Selection" below for available ids)
codex exec --sandbox workspace-write -m gpt-5.6-sol "your instruction" 2>&1

# Set reasoning effort (low, medium, high, xhigh) via inline config
codex exec --sandbox workspace-write -c model_reasoning_effort=xhigh "hard problem" 2>&1

# Combine model + reasoning effort
codex exec --sandbox workspace-write -m gpt-5.6-sol -c model_reasoning_effort=xhigh "your instruction" 2>&1

# Save output to file (writes codex's final message)
codex exec --sandbox workspace-write -o results.txt "analyze the architecture" 2>&1

# Work in a specific directory
codex exec --sandbox workspace-write -C /path/to/project "refactor the module" 2>&1
```

## Model Selection & Verification

**Available model ids** (as of 2026-07, `codex-cli 0.144.1`): `gpt-5.6-sol`,
`gpt-5.6-terra`, `gpt-5.6-luna`, `gpt-5.5`, `gpt-5.4`, `gpt-5.4-mini`,
`gpt-5.3-codex-spark`. Select with `-m <id>`. If you omit `-m`, codex uses the
`model` in `~/.codex/config.toml` (currently defaults to `gpt-5.6-sol`).
**`gpt-5.6-sol` is verified working via `codex exec`** (2026-07-10). Note
`gpt-5.4` is ALSO a real available model — relevant to the self-misID trap below.

Enumerate what's actually available on this box (models are stored under the
`slug` key, NOT `id`):
```bash
codex --version
python3 -c "import json; d=json.load(open('$HOME/.codex/models_cache.json')); print([m['slug'] for m in d['models']])"
grep -E '^model' ~/.codex/config.toml           # the current default
```

### ⚠️ The model MISREPORTS its own name — do not trust it

If you ask codex "what model are you?", `gpt-5.6-sol` will often answer
**"GPT-5.4"** (or similar). This is a routine LLM training-data artifact — models
are unreliable narrators of their own version. **It does NOT mean codex downgraded
or that 5.6-sol "isn't working."** Ignore the self-report entirely.

**To verify which model actually ran, use the two authoritative sources:**

1. **The run banner** printed at startup (stdout / the background `.output` file):
   ```
   model: gpt-5.6-sol
   sandbox: workspace-write ...
   session id: <uuid>
   ```
2. **Codex's own session rollout** (written by the CLI, independent of the
   banner) — grep the session file for the recorded model:
   ```bash
   # find the newest session and confirm the model it recorded
   f=$(ls -t ~/.codex/sessions/*/*/*/rollout-*.jsonl | head -1)
   grep -oE 'gpt-5\.[0-9]+(-sol|-terra|-luna)?' "$f" | sort -u
   ```
   A single `gpt-5.6-sol` here is proof — no 5.4/5.5 slug appears.

### If codex "isn't working" — checklist

- **Saw "GPT-5.4" in the reply?** That's the self-misID above, not a failure.
  Verify with the banner / rollout instead.
- **`--full-auto is deprecated` warning?** Harmless. Switch to
  `--sandbox workspace-write`.
- **Hangs with no output?** The Stdin Gotcha below — add `< /dev/null` (or a real
  file) as stdin.
- **`unknown model` / auth error?** Check `codex --version`, that you passed an
  exact id from the list above (e.g. `gpt-5.6-sol`, not `5.6-sol` or `sol`), and
  that codex is logged in (`codex login` status) with a plan that offers the model.
- **Different machine?** `config.toml`, auth, and `models_cache.json` are
  per-box — a model available on one host may not be on another; pass `-m`
  explicitly and enumerate as above.

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
# Bash({ command: 'codex exec --sandbox workspace-write "..." 2>&1', run_in_background: true })

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
codex exec --sandbox workspace-write "long task" 2>&1 | tail -100

# GOOD — let output stream to stdout (foreground) or to the background log file
codex exec --sandbox workspace-write "long task" < /dev/null 2>&1
```

For long runs use `run_in_background: true` and tail the output file the Bash
tool writes (`/tmp/.../<task-id>.output`) — that gives you intermediate
visibility without breaking codex's stdout pipe.

## Sandbox Limitations Codex Imposes

Codex's write sandbox (`--sandbox workspace-write`, and the deprecated
`--full-auto`) restricts what the spawned process can do, even inside the
workspace. Two limits matter for typical use:

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
