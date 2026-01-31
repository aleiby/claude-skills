#!/usr/bin/env bash
# complete-tackle.sh - Close root molecule and unhook after tackle completion
#
# Usage: source complete-tackle.sh
#
# Inputs (optional):
#   ISSUE_ID      - The issue bead ID (will be recovered from hook if not set)
#   MOL_ID        - The molecule ID to close (will be recovered from hook if not set)
#   SQUASH_SUMMARY - Summary for the digest (default: "Tackle complete")
#
# Side effects:
#   - Squashes the molecule (creates digest for audit trail)
#   - Stores digest ID in issue notes for future reference
#   - Closes the root molecule
#   - Verifies molecule is closed
#   - Unhooks the issue (frees hook for other work)
#
# Notes:
#   - Run this AFTER closing the reflect step
#   - The issue stays in "deferred" status until PR outcome - that's correct
#   - Molecules do NOT auto-close, this explicit close is required
#
# Errors: Exits 1 if molecule ID cannot be found

set -euo pipefail

# Get IDs from hook if not already set
HOOK_JSON=$(gt hook --json 2>/dev/null || echo '{}')
if [ -z "${ISSUE_ID:-}" ]; then
  ISSUE_ID=$(echo "$HOOK_JSON" | jq -r '.pinned_bead.id // empty')
fi
if [ -z "${MOL_ID:-}" ]; then
  MOL_ID=$(echo "$HOOK_JSON" | jq -r '.attached_molecule // empty')
fi

if [ -z "$MOL_ID" ]; then
  echo "ERROR: No molecule ID found. Check gt hook or context-recovery.sh output."
  exit 1
fi

# Squash molecule to create digest (preserves audit trail since wisps don't sync)
# The summary captures PR outcome for future learning
SQUASH_SUMMARY="${SQUASH_SUMMARY:-Tackle complete}"
DIGEST_OUTPUT=$(bd mol squash "$MOL_ID" --summary "$SQUASH_SUMMARY" --json 2>/dev/null || echo "{}")
DIGEST_ID=$(echo "$DIGEST_OUTPUT" | jq -r '.digest_id // empty' 2>/dev/null || echo "")

# Store digest ID in issue notes for future reference
if [ -n "$DIGEST_ID" ] && [ -n "${ISSUE_ID:-}" ]; then
  bd update "$ISSUE_ID" --append-notes "digest: $DIGEST_ID" 2>/dev/null || true
fi

# Close the root molecule
bd close "$MOL_ID" --reason "Tackle complete - PR submitted"

# Verify molecule closed and hook cleared
echo "Verifying molecule closure..."
gt hook  # Should show "Nothing on hook"

# Unhook the issue (frees your hook for other work)
# The issue stays in "deferred" status until PR outcome - that's correct.
# But you can work on other things while waiting for maintainer review.
gt unhook --force

echo "Tackle cleanup complete: molecule closed, hook cleared"
