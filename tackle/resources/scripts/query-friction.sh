#!/usr/bin/env bash
# query-friction.sh - Query issues with tackle friction for pattern detection
#
# Usage: source query-friction.sh
#        or: bash query-friction.sh
#
# Inputs: None
#
# Outputs:
#   Prints JSON of issues that had tackle friction, showing:
#   - id: issue ID
#   - title: issue title
#   - notes: friction details (recorded in issue notes)
#
# Use this to detect recurring issues before proposing skill fixes.
# Rule: 2+ occurrences = propose fix, 3+ = definitely fix
#
# Note: Friction is stored on the ISSUE bead (permanent), not the molecule
# (ephemeral wisp). This ensures friction history survives molecule GC.

set -euo pipefail

# Find issues that had tackle friction
bd list --all --label "tackle:friction" --json 2>/dev/null | jq '
  .[] | {id, title, notes}
'
