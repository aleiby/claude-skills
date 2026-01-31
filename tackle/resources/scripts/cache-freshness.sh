#!/usr/bin/env bash
# cache-freshness.sh - Check project research cache validity
#
# Usage: source cache-freshness.sh
#
# Inputs (required):
#   ORG_REPO - The org/repo to check cache for (e.g., "steveyegge/beads")
#
# Outputs (exported variables):
#   CACHE_BEAD  - The cache bead ID (or empty if not found)
#   CACHE_FRESH - "true" if cache is less than 24 hours old, "false" otherwise
#
# Dependencies: bd, jq
#
# Notes:
#   - Cross-platform date parsing (handles GNU date on Linux, BSD date on macOS)
#   - Handles timestamps with Z suffix or +/-HH:MM timezone offset

set -euo pipefail

# ORG_REPO must be provided by caller or auto-detected
# Note: This script runs BEFORE sling, so set-vars.sh cannot be used
if [ -z "${ORG_REPO:-}" ]; then
  # Auto-source detect-upstream.sh if ORG_REPO not set
  SCRIPT_DIR="${SKILL_DIR:-$HOME/.claude/skills/tackle}/resources/scripts"
  if [ -f "$SCRIPT_DIR/detect-upstream.sh" ]; then
    source "$SCRIPT_DIR/detect-upstream.sh"
  else
    echo "ERROR: ORG_REPO must be set before sourcing cache-freshness.sh"
    echo "Hint: source detect-upstream.sh && source cache-freshness.sh"
    exit 1
  fi
fi

# Fast path: Check config for cached bead ID
# Note: bd config get returns "key (not set)" when missing, not empty
CACHE_BEAD=$(bd config get "tackle.cache_bead.$ORG_REPO" 2>/dev/null | grep -v "(not set)" || echo "")

# Fallback: Label search if not in config - get most recently updated
if [ -z "$CACHE_BEAD" ] || [ "$CACHE_BEAD" = "null" ]; then
  # Sort by updated_at descending to get the freshest cache bead
  CACHE_BEAD=$(bd list --label=tackle-cache --title-contains="$ORG_REPO" --json 2>/dev/null | jq -r 'sort_by(.updated_at) | reverse | .[0].id // empty' || echo "")
fi

# Check freshness (24h threshold)
CACHE_FRESH=false
if [ -n "$CACHE_BEAD" ] && [ "$CACHE_BEAD" != "null" ]; then
  LAST_CHECKED=$(bd show "$CACHE_BEAD" --json 2>/dev/null | jq -r '.[0].notes' | grep -oE 'last_checked: [^ ]+' | sed 's/last_checked: //' || echo "")
  if [ -n "$LAST_CHECKED" ]; then
    # Cross-platform date parsing (handles +TZ offset, Z suffix, or bare timestamp)
    # Strip timezone suffix for parsing: remove trailing Z, or +/-HH:MM offset
    BARE_TS=$(echo "$LAST_CHECKED" | sed -E 's/(Z|[+-][0-9]{2}:[0-9]{2})$//')
    if date -d "$LAST_CHECKED" +%s >/dev/null 2>&1; then
      # GNU date (Linux)
      LAST_TS=$(date -d "$LAST_CHECKED" +%s)
    elif date -j -f "%Y-%m-%dT%H:%M:%S" "$BARE_TS" +%s >/dev/null 2>&1; then
      # BSD date (macOS) - use stripped timestamp
      LAST_TS=$(date -j -f "%Y-%m-%dT%H:%M:%S" "$BARE_TS" +%s)
    else
      LAST_TS=0
    fi
    NOW_TS=$(date +%s)
    AGE_HOURS=$(( (NOW_TS - LAST_TS) / 3600 ))
    [ "$AGE_HOURS" -lt 24 ] && CACHE_FRESH=true
  fi
fi

# Export variables for use by calling script
export CACHE_BEAD CACHE_FRESH
