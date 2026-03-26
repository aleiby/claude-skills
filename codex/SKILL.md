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
- **Read-only**: `codex exec --ask-for-approval never "instruction"` — can only
  read. Use for code reviews, doc reviews, analysis.

## Quick Reference

```bash
# Default (full-auto) — can make changes
codex exec --full-auto "fix the failing tests" 2>&1

# Read-only — reviews, analysis, second opinions
codex exec --ask-for-approval never "review src/ for security issues" 2>&1

# Pipe context in
echo "review this diff:" | cat - <(git diff) | codex exec --ask-for-approval never - 2>&1

# Use a specific model
codex exec --full-auto -m gpt-5-codex "your instruction" 2>&1

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
codex exec "Review docs/design/ for inconsistencies. Report issues with file paths and line numbers." 2>&1
```

## Common Uses

- **Code review:** `codex exec "review this PR diff for bugs" < <(git diff main)`
- **Doc review:** `codex exec "check docs/ for contradictions and stale references"`
- **Debug help:** `codex exec "why might this test be flaky?" < test_output.log`
- **Architecture:** `codex exec "suggest how to refactor this module" < src/module.py`
- **Research:** `codex exec "what are the tradeoffs of approach A vs B for X?"`
