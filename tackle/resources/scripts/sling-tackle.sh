#!/usr/bin/env bash
# sling-tackle.sh - Sling tackle formula onto issue and set up molecule
#
# Usage: source sling-tackle.sh
#
# Inputs (required):
#   ISSUE_ID        - The issue bead ID to tackle
#   ORG_REPO        - The upstream org/repo (e.g., "steveyegge/beads")
#   DEFAULT_BRANCH  - The default branch (e.g., "main")
#   UPSTREAM_REF    - The full ref (e.g., "upstream/main")
#   UPSTREAM_REMOTE - The git remote name (e.g., "upstream")
#
# Outputs (exported variables):
#   MOL_ID     - The created molecule ID
#   FIRST_STEP - The first ready step ID (may be empty)
#
# Side effects:
#   - Updates issue with upstream context
#   - Slings tackle formula (creates molecule, hooks issue)
#   - Claims first step with current actor
#
# Note: Steps are linked to molecule via parent-child deps.
#   Use gt hook --json to find ready steps (see .progress.ready_steps).
#
# Errors: Exits 1 with guidance if sling fails or BD_ACTOR not set

set -euo pipefail

# Verify required variables
if [ -z "${ISSUE_ID:-}" ]; then
  echo "ERROR: ISSUE_ID must be set before sourcing sling-tackle.sh"
  exit 1
fi

# Validate bead is accessible BEFORE doing any setup work
# This catches routing issues early (e.g., bead created in wrong database)
if ! bd show "$ISSUE_ID" --json >/dev/null 2>&1; then
  echo "ERROR: Cannot access bead '$ISSUE_ID'"
  echo ""
  echo "Possible causes:"
  echo "  - Bead was created with wrong prefix (check bd list to find it)"
  echo "  - Routing misconfiguration (run: BD_DEBUG_ROUTING=1 bd show $ISSUE_ID)"
  echo "  - Bead doesn't exist (was it created?)"
  echo ""
  echo ">>> Mail the mayor - do NOT debug this yourself <<<"
  exit 1
fi

if [ -z "${ORG_REPO:-}" ]; then
  echo "ERROR: ORG_REPO must be set before sourcing sling-tackle.sh"
  exit 1
fi
if [ -z "${DEFAULT_BRANCH:-}" ]; then
  echo "ERROR: DEFAULT_BRANCH must be set before sourcing sling-tackle.sh"
  exit 1
fi
if [ -z "${UPSTREAM_REF:-}" ]; then
  echo "ERROR: UPSTREAM_REF must be set before sourcing sling-tackle.sh"
  exit 1
fi
if [ -z "${UPSTREAM_REMOTE:-}" ]; then
  echo "ERROR: UPSTREAM_REMOTE must be set before sourcing sling-tackle.sh"
  exit 1
fi

# Store upstream context in the issue bead (bead carries its own context)
# This is needed because gt sling --on doesn't support --var
# Other scripts use set-vars.sh to read these back
bd update "$ISSUE_ID" --notes "upstream: $ORG_REPO
default_branch: $DEFAULT_BRANCH
upstream_ref: $UPSTREAM_REF
upstream_remote: $UPSTREAM_REMOTE"

# Sling the issue with tackle formula
# This creates the molecule wisp, bonds it to the issue, hooks issue to self,
# and stores attached_molecule in the issue bead's description
gt sling tackle --on "$ISSUE_ID"

# Verify hook is set
if ! gt hook --json 2>/dev/null | jq -e '.attached_molecule' > /dev/null; then
  echo "ERROR: Sling failed - no molecule attached"
  echo "Check gt sling output above for errors"
  echo ">>> Mail the mayor (see 'When Things Go Wrong' above) - do NOT try to fix this yourself <<<"
  exit 1
fi

# Get molecule ID and first step from hook (avoids bd routing issues)
HOOK_JSON=$(gt hook --json)
MOL_ID=$(echo "$HOOK_JSON" | jq -r '.attached_molecule')
echo "Tackle started: $MOL_ID"

# Add formula label for pattern detection in reflect phase
bd update "$MOL_ID" --add-label "formula:tackle"

# Claim first step with assignee for status tracking
FIRST_STEP=$(echo "$HOOK_JSON" | jq -r '.progress.ready_steps[0] // empty')
if [ -n "$FIRST_STEP" ]; then
  if [ -z "${BD_ACTOR:-}" ]; then
    echo "ERROR: BD_ACTOR not set. Run env-check.sh first, or report to mayor."
    exit 1
  fi
  bd update "$FIRST_STEP" --status=in_progress --assignee "$BD_ACTOR"
fi

# Export for use by calling context
export MOL_ID FIRST_STEP
