#!/usr/bin/env bash
# set-vars.sh - Load tackle context variables from bead notes
#
# Usage: source set-vars.sh
#
# Inputs: None (reads from gt hook and bd)
#
# Outputs (exported variables):
#   ISSUE_ID       - The issue bead ID from the hook
#   MOL_ID         - The molecule ID attached to the hook
#   ORG_REPO        - The upstream org/repo (e.g., "steveyegge/beads")
#   DEFAULT_BRANCH  - The default branch (e.g., "main")
#   UPSTREAM_REF    - The full ref (e.g., "upstream/main")
#   UPSTREAM_REMOTE - The git remote name (e.g., "upstream")
#   PR_NUMBER       - The PR number (optional, only after gate-submit)
#   BUILD_CMD       - Build command from cached research (e.g., "go build ./...", "npm run build")
#   TEST_CMD        - Test command from cached research (e.g., "go test ./...", "npm test")
#   LINT_CMD        - Lint command from cached research (e.g., "go vet ./...", "npm run lint")
#
# Notes:
#   - Variables are stored in bead notes by sling-tackle.sh
#   - This is a lightweight read (one bd show call)
#   - Errors if notes are missing (sling-tackle.sh must run first)

set -euo pipefail

# Get IDs from hook
# Capture both stdout and stderr to diagnose failures
HOOK_ERR=$(mktemp)
HOOK_JSON=$(gt hook --json 2>"$HOOK_ERR") || true
HOOK_ERR_MSG=$(cat "$HOOK_ERR")
rm -f "$HOOK_ERR"

# Handle gt hook failures
if [ -z "$HOOK_JSON" ] || [ "$HOOK_JSON" = "{}" ]; then
  echo "ERROR: No issue on hook. Is this a tackle session?"
  if [ -n "$HOOK_ERR_MSG" ]; then
    echo "Details: $HOOK_ERR_MSG"
  fi
  echo ""
  echo "If you switched branches, run: /tackle --resume"
  echo "To check hook status: gt hook"
  exit 1
fi

ISSUE_ID=$(echo "$HOOK_JSON" | jq -r '.pinned_bead.id // .bead_id // empty')
MOL_ID=$(echo "$HOOK_JSON" | jq -r '.attached_molecule // empty')

if [ -z "$ISSUE_ID" ]; then
  echo "ERROR: Hook exists but has no bead_id"
  echo "Hook JSON: $HOOK_JSON"
  echo ""
  echo "Try: /tackle --resume"
  exit 1
fi

# Read notes from bead
NOTES=$(bd show "$ISSUE_ID" --json 2>/dev/null | jq -r '.[0].notes // empty')

# Parse variables from notes
ORG_REPO=$(echo "$NOTES" | grep -oP '^upstream: \K.+' || echo "")
DEFAULT_BRANCH=$(echo "$NOTES" | grep -oP '^default_branch: \K.+' || echo "")
UPSTREAM_REF=$(echo "$NOTES" | grep -oP '^upstream_ref: \K.+' || echo "")
UPSTREAM_REMOTE=$(echo "$NOTES" | grep -oP '^upstream_remote: \K.+' || echo "")
PR_NUMBER=$(echo "$NOTES" | grep -oP '^pr_number: \K.+' || echo "")

# Verify required vars are present (PR_NUMBER is optional - only exists after gate-submit)
if [ -z "$ORG_REPO" ] || [ -z "$DEFAULT_BRANCH" ] || [ -z "$UPSTREAM_REF" ] || [ -z "$UPSTREAM_REMOTE" ]; then
  echo "ERROR: Missing tackle context in bead notes for $ISSUE_ID"
  echo "Expected: upstream, default_branch, upstream_ref, upstream_remote"
  echo "Found: $(echo "$NOTES" | head -4)"
  exit 1
fi

# Load build/test/lint commands from cached research bead
CACHE_BEAD=$(bd list --label=tackle-cache --title-contains="$ORG_REPO" --json 2>/dev/null | jq -r 'sort_by(.updated_at) | reverse | .[0].id // empty' || echo "")
if [ -n "$CACHE_BEAD" ] && [ "$CACHE_BEAD" != "null" ]; then
  CACHE_DESC=$(bd show "$CACHE_BEAD" --json 2>/dev/null | jq -r '.[0].description // empty')
  BUILD_CMD=$(echo "$CACHE_DESC" | grep -A2 'build:' | grep -oP '^\s*command: "\K[^"]+' | head -1 || echo "")
  TEST_CMD=$(echo "$CACHE_DESC" | grep -A5 'testing:' | grep -oP 'commands: \["\K[^"]+' | head -1 || echo "")
  LINT_CMD=$(echo "$CACHE_DESC" | grep -A2 'coding_style:' | grep -oP '^\s*linter: "\K[^"]+' | head -1 || echo "")
else
  BUILD_CMD=""
  TEST_CMD=""
  LINT_CMD=""
fi

# Export all variables (PR_NUMBER, BUILD_CMD, TEST_CMD, LINT_CMD may be empty)
export ISSUE_ID MOL_ID ORG_REPO DEFAULT_BRANCH UPSTREAM_REF UPSTREAM_REMOTE PR_NUMBER BUILD_CMD TEST_CMD LINT_CMD
