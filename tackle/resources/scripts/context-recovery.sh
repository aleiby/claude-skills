#!/usr/bin/env bash
# context-recovery.sh - Recover tackle context after session restart
#
# Usage: source context-recovery.sh
#
# Inputs: None (reads from gt hook and bd)
#
# Outputs (exported variables):
#   ISSUE_ID        - The issue bead ID from the hook
#   MOL_ID          - The molecule ID attached to the hook
#   ORG_REPO        - The upstream org/repo from issue notes
#   DEFAULT_BRANCH  - The default branch (e.g., "main")
#   UPSTREAM_REF    - The full ref (e.g., "upstream/main")
#   UPSTREAM_REMOTE - The git remote name (e.g., "upstream")
#   PR_NUMBER       - The PR number (optional, only after gate-submit)
#   STEP_ID         - The current ready step ID
#   STEP_TITLE      - The step title (e.g., "[PLAN] Run /tackle --resume plan")
#
# Errors: Exits 1 if upstream not found in issue notes or git remotes
#
# Notes:
#   - Run this after session restart (compaction, handoff, new terminal)
#   - Shows progress via gt hook --json
#   - Uses set-vars.sh for core variable loading

set -euo pipefail

# Load core variables (ISSUE_ID, MOL_ID, ORG_REPO, DEFAULT_BRANCH, UPSTREAM_REF)
SCRIPT_DIR="${SKILL_DIR:-$HOME/.claude/skills/tackle}/resources/scripts"
source "$SCRIPT_DIR/set-vars.sh"

# Get current step from hook
HOOK_JSON=$(gt hook --json 2>/dev/null || echo '{}')
STEP_ID=$(echo "$HOOK_JSON" | jq -r '.progress.ready_steps[0] // empty')
if [ -n "$STEP_ID" ]; then
  STEP_TITLE=$(bd show "$STEP_ID" --json 2>/dev/null | jq -r '.[0].title // empty')
else
  STEP_TITLE=""
fi

# Show progress
gt hook --json | jq '.progress'

# Export step context (core vars already exported by set-vars.sh)
export STEP_ID STEP_TITLE
