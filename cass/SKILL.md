# CASS - Coding Agent Session Search

## Overview

Search past coding agent conversations locally. CASS indexes Claude Code, Codex, Cursor, Gemini CLI, and other agent session histories into a full-text search index.

**Binary**: `/home/aleiby/.local/bin/cass`
**Data**: `~/.local/share/coding-agent-search/`

## When to Use

- Finding how something was solved in a previous session
- "Did we already do X?" / "How did we handle Y last time?"
- Searching for past decisions, implementations, or debugging sessions
- Finding which session touched a specific file or topic

## Quick Reference

```bash
# Search (robot mode for structured output)
cass search "timer alarm" --robot --limit 5

# Filter by time
cass search "refactoring" --today
cass search "bug fix" --week
cass search "api" --days 30
cass search "feature" --since 2025-01-01

# Filter by workspace
cass search "error" --workspace /home/aleiby/gt/ocws/crew/TARS

# Aggregate overview (99% token reduction)
cass search "error" --json --aggregate agent
cass search "*" --json --aggregate date --week

# Follow up on a search hit
cass view /path/to/session.jsonl -n 42 -C 10

# Re-index after new sessions
cass index --full

# Health check
cass health
```

## Agent Usage Pattern

For minimal token usage, use `--robot --fields minimal --limit 5`:
```bash
cass search "your query" --robot --fields minimal --limit 5
```

For more context, use `--fields summary` or fetch full content with `cass view`.

## Notes

- The `onnxruntime cpuid_info warning` on ARM64 is harmless — ignore it
- `--robot` auto-suppresses info logs and outputs JSON
- Use `cass robot-docs <topic>` for detailed reference (topics: commands, env, paths, schemas, guide, exit-codes, examples, contracts, wrap, sources)
