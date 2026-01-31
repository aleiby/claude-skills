---
name: tackle
description: |
  Upstream-aware issue implementation workflow with mandatory approval gates.
  Checks upstream for existing fixes. Enforces review gates before PR submission.

  INVOKE THIS SKILL when user says "tackle" in any form:
  - "tackle", "let's tackle", "tackle this", "tackle the X issue"
user-invocable: true
---

# Tackle - Upstream-Aware Implementation Workflow

## Quick Reference

```
/tackle <issue>         Start or resume tackle for issue (auto-resumes if prior progress exists)
/tackle --resume        Continue after compaction/restart (auto-detects step from hook)
/tackle --resume <step> Load guidance for specific step (plan, implement, validate, etc.)
/tackle --status        Show current state
/tackle --pause         Pause tackle (keeps progress, frees hook for other work)
/tackle --abort         Abandon tackle permanently (destroys molecule, cannot resume)
/tackle --refresh       Force refresh upstream research
/tackle --help          Show this help
```

When user asks for help, show this Quick Reference section.

## When Things Go Wrong

**STOP. Do not try to fix skill/workflow problems yourself.**

If you encounter:
- Script errors or unexpected failures
- Commands that don't work as documented
- Confusing or contradictory instructions
- State that doesn't match what's expected
- Workflow that seems stuck or broken

**Do this instead:**

1. **Stop immediately** - Don't retry, work around, or guess at fixes
2. **Mail the mayor** with:
   - What step you were on
   - What you tried to do
   - The exact error or unexpected behavior
   - Relevant state (`gt hook --json`)
3. **Wait for guidance** - The mayor will investigate and fix the skill

```bash
# Report problem to mayor
STEP="gate-submit"  # Current step
ERROR_DESC="ci-status-check.sh failed with unexpected error"
ERROR_MSG="jq: error: Cannot iterate over null"  # Optional
source "$SKILL_DIR/resources/scripts/report-problem.sh"
```

**Why this matters:** Attempting to fix workflow problems mid-tackle often makes things worse. Problems reported to the mayor get fixed in the skill itself, helping all future runs.

## Common Mistakes

**Don't skip step resource files.** Even "simple" steps like record and reflect have scripts that handle edge cases:

| Step | Resource | Required Script |
|------|----------|-----------------|
| record | SUBMIT.md | `source record-pr-stats.sh` (sets label + status) |
| reflect | REFLECT.md | `source complete-tackle.sh` (squash + unhook) |

Manual `bd update` commands will miss side effects like `--status=deferred`. Always use the provided scripts.

**Note:** Sub-agent resources (PROJECT-RESEARCH.md, etc.) are loaded conditionally by sub-agents - don't load those in the main agent.

## Resumption Protocol (ALWAYS FIRST)

**When to run this:** After session restart (compaction, handoff, new terminal), or when checking status with `/tackle --status`. This ensures you have accurate state before taking any action.

**NEVER trust summary alone. State is truth.**

### SKILL_DIR (Required)

Before running any tackle scripts, set `SKILL_DIR` to the directory containing this SKILL.md file:

```bash
SKILL_DIR="<path-to-tackle-skill-directory>"  # Set this based on where you loaded the skill
```

All subsequent `source` commands use `$SKILL_DIR`. Preserve this variable throughout the tackle session.

### Environment Check

Verify required environment variables are set (especially after compaction):

```bash
source "$SKILL_DIR/resources/scripts/env-check.sh"
```

**Checks**: `BD_ACTOR` (built-in), `SKILL_DIR` (set above)

**If BD_ACTOR is missing**: This may be a compaction bug. Report to mayor.

### Context Recovery

Recover all variables needed for tackle execution:

```bash
source "$SKILL_DIR/resources/scripts/context-recovery.sh"
```

This sets: `ISSUE_ID`, `MOL_ID`, `ORG_REPO`, `STEP_ID`, `STEP_TITLE`

**Errors**: Exits 1 if upstream not found in issue notes or git remotes.

### On Errors

**If any resumption step fails unexpectedly: See "When Things Go Wrong" above.** Don't debug - mail the mayor.

## Resource Loading (Progressive Disclosure)

**DO NOT load all resource files.** Load only what's needed for your current step.

Resources are in the `resources/` folder relative to this SKILL.md file.

After running context-recovery.sh, use `STEP_TITLE` to determine which resource to load.
Parse phase from title like `[PLAN] Run /tackle --resume plan`.

Use this lookup:

| Step | Resource |
|------|----------|
| plan | IMPLEMENT.md (Plan Phase) |
| gate-plan | This file (APPROVAL GATES) |
| branch | IMPLEMENT.md (Branch Phase) |
| implement | IMPLEMENT.md (Implement Phase) |
| validate | VALIDATION.md |
| gate-submit | This file (APPROVAL GATES) |
| submit | SUBMIT.md |
| record | SUBMIT.md (Record Phase) |
| reflect | REFLECT.md |

**Sub-agent resources (sub-agents load their own):**
- `<skill-dir>/resources/subagents/PROJECT-RESEARCH.md`
- `<skill-dir>/resources/subagents/ISSUE-RESEARCH.md`
- `<skill-dir>/resources/subagents/PR-CHECK.md`

**Pre-molecule research:** Handled by sub-agents (see Sub-Agent Usage below). Main agent only loads compact YAML results.

## Sub-Agent Usage (Context Optimization)

**Use sub-agents for research phases** to reduce context in the main conversation. Sub-agents load their own resource files, execute API calls, and return compact structured summaries.

### When to Use Sub-Agents

| Phase | Sub-Agent? | Reason |
|-------|------------|--------|
| Project Research (Step 4) | **Yes** | Only when cache stale; fetches lots of API data |
| Pending PR Check (Step 6) | **Yes** | Runs every tackle, loops through multiple issues |
| Issue Research (Step 7) | **Yes** | Runs every tackle, checks multiple repos |
| Implementation | No | Needs full codebase context |
| Gates | No | Requires user interaction |

**Important:** Cache freshness checks stay in SKILL.md to avoid spawning sub-agents unnecessarily.

## Phase Flow

```
Pre-molecule (research):
  - Detect Upstream
  - [Project Research → Project Report] (only if cache stale)
  - Issue Research (checks all tracked repos)
      → Existing Work Decision → (skip | wait | proceed)
  - Sling Issue with Tackle Formula

Molecule steps (implementation):
  Plan → GATE:Plan
    → Branch → Implement → Validate → GATE:Submit
      → Submit → Record → Reflect
```

## Execution Instructions

### Parse Command

First, parse what the user wants:

| Input | Action |
|-------|--------|
| `/tackle <issue>` | Start or resume tackle for issue (auto-hooks and resumes if prior progress exists) |
| `/tackle --resume` | Continue in-progress tackle after compaction/restart (runs Resumption Protocol) |
| `/tackle --status` | Show current tackle state via `gt hook --json` |
| `/tackle --pause` | Pause tackle, keep progress for later resume |
| `/tackle --abort` | Abandon tackle permanently, destroy molecule |
| `/tackle --refresh` | Force refresh upstream research |
| `/tackle --help` | Show Quick Reference to user |

### Starting Tackle

When starting `/tackle <issue>`:

#### 1. Resolve Issue

The user's input may be an issue ID, partial match, or description.

```bash
# Try direct lookup (use || true to avoid exit on not found)
bd show <issue> || true
```

If not found, search for matches:
```bash
bd ready -n 0 --json | jq -r '.[] | "\(.id): \(.title)"'
```

If no matches, offer to create a bead for the work.

Once resolved, set the variable for subsequent steps:
```bash
ISSUE_ID="<resolved-issue-id>"  # e.g., "hq-1234"
```

#### 2. Check for Existing Work

Check if the resolved issue already has an attached molecule (prior tackle progress):

```bash
# Check if issue has an attached molecule
ATTACHED_MOL=$(bd show "$ISSUE_ID" --json | jq -r '.[0].description // ""' | grep -oP 'attached_molecule: \K\S+' || true)

# Check what's currently on hook
HOOKED_BEAD=$(gt hook --json | jq -r '.pinned_bead.id // empty')
```

**If issue has an attached molecule:**
- If `$ISSUE_ID` is already on hook → resume from current step (run Resumption Protocol)
- If different bead is hooked → ask user to unsling first, or auto-hook:
  ```bash
  gt hook "$ISSUE_ID"  # Hooks the issue (with its attached molecule)
  ```
  Then run the Resumption Protocol to continue where it left off.

**If no molecule attached:** Continue with fresh tackle setup below.

#### 3. Detect Upstream

```bash
source "$SKILL_DIR/resources/scripts/detect-upstream.sh"
```

This sets: `UPSTREAM_REMOTE`, `UPSTREAM_URL`, `ORG_REPO`, `DEFAULT_BRANCH`, `UPSTREAM_REF`

**Errors**: Exits 1 if no valid remote found or URL cannot be parsed.

Variables set:
- `$UPSTREAM_REMOTE` - the git remote name (upstream, fork-source, or origin)
- `$UPSTREAM_URL` - the remote URL
- `$ORG_REPO` - the org/repo format (e.g., "steveyegge/beads")
- `$DEFAULT_BRANCH` - the default branch name (e.g., "main")
- `$UPSTREAM_REF` - the full ref (e.g., "upstream/main")

**Placeholder aliases used in this skill:**

Angle-bracket placeholders indicate values to substitute with actuals:
- `<upstream>` = `$ORG_REPO` (e.g., "steveyegge/beads")
- `<issue-id>` = the local bead ID being tackled
- `<molecule-id>` = the tackle molecule ID (gt-mol-xxx)
- `<skill-dir>` = directory where this skill was loaded from
- `<cache-bead-id>` = cache bead ID from Step 4
- `<pending-issues-json>` = JSON array from PENDING_JSON
- `<tracked-repos-json>` = JSON array from TRACKED_REPOS
- `<search-terms-array>` = keywords extracted from issue title
- `<upstream-issue-number>` = GitHub issue number (or null)
- `<upstream-pr-url>` = the draft PR URL on upstream repo

**Sub-agent prompts:** Replace all `<placeholders>` with actual values before spawning - sub-agents don't inherit shell variables.

#### 4. Project Research (cache check + sub-agent if stale)

Check if project-level research cache needs refreshing.

**Cache freshness check (stays in main agent):**
```bash
source "$SKILL_DIR/resources/scripts/cache-freshness.sh"
```

This sets: `CACHE_BEAD`, `CACHE_FRESH`

**Requires**: `ORG_REPO` must be set.

**If cache is fresh:** Skip to Step 6 (Pending PR Check).

**If cache is stale or missing:** Invoke sub-agent:
```
Use Task tool with:
  subagent_type: "general-purpose"
  prompt: |
    Read resource file: <skill-dir>/resources/subagents/PROJECT-RESEARCH.md

    Execute with inputs:
    ```yaml
    inputs:
      org_repo: "<upstream>"
      cache_bead: "<cache-bead-id>"  # or "null" if not found
    ```

    Return structured YAML as specified in the resource file.
```

#### 5. Project Report (only if new data found)

If project research sub-agent ran, present checkpoint with the returned data:
- Guidelines summary
- Related repos detected (offer to track)

User can add more related repos or continue to Step 6.

#### 6. Check Pending PR Outcomes (Sub-Agent)

**Before proceeding with any new work, clean up stale PR submissions.**

This is a housekeeping gate - check ALL issues with `pr-submitted` label.

**Gather inputs for sub-agent:**
```bash
# Build pending issues list
# Notes contain "PR: https://github.com/org/repo/pull/123" format
# Extract PR number from the URL path
PENDING_JSON=$(bd list --label=pr-submitted --limit 0 --json 2>/dev/null | jq '[.[] | {
  id: .id,
  pr_number: ((.notes // "") | capture("pull/(?<n>[0-9]+)")? | .n // null),
  title: .title
}] | map(select(.pr_number))')

echo "$PENDING_JSON"
```

**Invoke sub-agent:**
```
Use Task tool with:
  subagent_type: "general-purpose"
  prompt: |
    Read resource file: <skill-dir>/resources/subagents/PR-CHECK.md

    Execute with inputs:
    ```yaml
    inputs:
      org_repo: "<upstream>"
      pending_issues: <pending-issues-json>
    ```

    Return structured YAML as specified in the resource file.
```

**Handle result:**
The sub-agent returns a `pr_check` YAML with `summary` and `actions_taken`.

Report to user:
```
Checked N pending PR(s): <actions_taken summary>
```

If no pending PRs, sub-agent returns `checked_count: 0` - report explicitly.

#### 7. Issue Research (Sub-Agent)

**Check if the current issue is already addressed.**

**Gather inputs for sub-agent:**
```bash
# Get tracked repos from config (stored via: bd config set tackle.tracked_repos '["org/repo1","org/repo2"]')
TRACKED_REPOS=$(bd config get tackle.tracked_repos 2>/dev/null || echo '[]')
# Falls back to just ORG_REPO if no cache
[ "$TRACKED_REPOS" = "[]" ] || [ -z "$TRACKED_REPOS" ] && TRACKED_REPOS="[\"$ORG_REPO\"]"

# Extract upstream issue number from external_ref field
# Format convention: "gh:<org>/<repo>#<number>" or "issue:<number>" for simple cases
# Examples: "gh:steveyegge/beads#123", "issue:456"
# Set via: bd create --external-ref "gh:org/repo#123" or bd update --external-ref "..."
UPSTREAM_ISSUE=$(bd show "$ISSUE_ID" --json | jq -r '.[0].external_ref // empty' | grep -oE '#[0-9]+$|issue:[0-9]+' | grep -oE '[0-9]+')

# Extract search terms from issue title
ISSUE_TITLE=$(bd show "$ISSUE_ID" --json | jq -r '.[0].title')
```

**Invoke sub-agent:**
```
Use Task tool with:
  subagent_type: "general-purpose"
  prompt: |
    Read resource file: <skill-dir>/resources/subagents/ISSUE-RESEARCH.md

    Execute with inputs:
    ```yaml
    inputs:
      org_repo: "<upstream>"
      tracked_repos: <tracked-repos-json>
      issue_id: "<issue-id>"
      upstream_issue: <upstream-issue-number>  # or null if not set
      search_terms: <search-terms-array>
    ```

    Return structured YAML as specified in the resource file.
```

**Handle result:**
The sub-agent returns an `issue_research` YAML with `decision` and `reason`.

Use the `decision` field to determine next action:
- `proceed` → Continue to Step 8 (create molecule)
- `skip` → Present skip option to user
- `wait` → Present wait option with `blocking_work` details
- `fix_existing` → Present fix option with user's open PR details

#### 8. Existing Work Decision

If existing work found, present options:

```
Found existing work for this issue:
  - Upstream issue #123 is CLOSED
  - PR #456 already addresses this
  - You have PR #789 open (CI failing)

Options:
  - Skip tackle (close local issue)
  - Wait for existing PR to merge
  - Fix your existing PR
  - Proceed anyway
```

Accept natural language responses. If user chooses to skip/wait, do not create molecule.

#### 9. Sync Formula

Before creating the molecule, install the formula to town-level (user formulas, not project-specific):

```bash
# <skill-dir> is the directory containing SKILL.md (where you loaded this skill from)
FORMULA_SRC="<skill-dir>/resources/tackle.formula.toml"

# Install to town-level formulas (Tier 2 - cross-project, user workflows)
# GT_TOWN_ROOT is set by Gas Town, defaults to ~/gt
TOWN_FORMULAS="${GT_TOWN_ROOT:-$HOME/gt}/.beads/formulas"
mkdir -p "$TOWN_FORMULAS"
cp "$FORMULA_SRC" "$TOWN_FORMULAS/tackle.formula.toml"
```

#### 10. Sling Issue with Tackle Formula (only if proceeding)

**⚠️ PRE-FLIGHT CHECKLIST - Do not proceed until all items are checked:**

Before slinging the issue, verify you completed these steps:

- [ ] **Step 6 (Pending PR Check)** - Successfully ran PR-CHECK sub-agent to clean up stale submissions
- [ ] **Step 7 (Issue Research)** - Successfully ran ISSUE-RESEARCH sub-agent to check for existing work
- [ ] **Step 8 (Existing Work Decision)** - If existing work found, user confirmed to proceed

If you skipped any of these, **STOP and go back to the associated step(s)**. Duplicating work wastes maintainer time and may get your PR rejected. The sub-agents exist to offload this research from your context - use them.

```bash
source "$SKILL_DIR/resources/scripts/sling-tackle.sh"
```

This sets: `MOL_ID`, `FIRST_STEP`

**Requires**: `ISSUE_ID`, `ORG_REPO`, `BD_ACTOR` must be set.

### Phase Execution

Based on current step (from `gt hook --json`), take the appropriate action.
See Resource Loading table above for which resource file to load.

| Step ID | Action |
|---------|--------|
| `plan` | Create implementation plan |
| `gate-plan` | **STOP** - Wait for plan approval |
| `branch` | Create clean branch from upstream |
| `implement` | Write code following upstream conventions |
| `validate` | Run tests, check isolation |
| `gate-submit` | **STOP** - Wait for submit approval |
| `submit` | Mark draft PR ready for review |
| `record` | Update local issue with PR link |
| `reflect` | Reflect on skill issues (see Reflect section) |

### Completing Steps

After completing work for a step:
```bash
bd close "$STEP_ID" --continue
NEXT_STEP=$(gt hook --json | jq -r '.progress.ready_steps[0] // empty')
```

**Continue until reflect is complete and root molecule is closed.** Tackle is not done until then.

---

## APPROVAL GATES

**CRITICAL SAFETY RULES - READ THIS SECTION COMPLETELY**

### Response Detection

Accept natural language **approval**:
- "approve", "approved", "proceed", "continue"
- "yes", "lgtm", "looks good", "go ahead"
- "submit", "ship it" (at gate-submit only)

Accept natural language **explain** (gate-plan only):
- "explain", "why", "rationale", "reasoning"
- "tell me more", "justify", "alternatives"

Accept natural language **decline**:
- "decline", "reject", "no", "stop"
- "wait", "revise", "hold", "change"

### Gate Rules (NEVER VIOLATE)

1. **NEVER** proceed past a gate without explicit user approval
2. **NEVER** auto-approve based on heuristics or timeouts
3. **NEVER** submit a PR without gate-submit approval
4. **ALL agents** stop at gates - no exceptions
5. If no human in loop, **WAIT INDEFINITELY** at the gate

---

## Gate 1: `gate-plan` (Plan Review)

**MANDATORY STOP** - Present the plan, then wait for explicit user approval before proceeding.

### Pre-Gate Preparation (Internal)

Before presenting the checkpoint, prepare internally (but don't show unless asked):

1. **Why this approach over alternatives** - What other solutions were considered? Why were they rejected?
2. **Key tradeoffs** - What are we accepting? Why is it acceptable?
3. **Root cause confidence** - How does this address the actual problem, not just symptoms?

Only present this if the user asks to "explain".

### Show to User

```
┌────────────────────────────────────────────────────────────────────┐
│  📝 CHECKPOINT: Plan Review                                        │
└────────────────────────────────────────────────────────────────────┘

Plan for <issue-id>: <issue-title>

## Scope
  - Files: <list of files to modify>
  - Estimated changes: ~<n> lines

## Approach
<brief description of implementation approach>

## Upstream Context
  - Conflicting PRs: <none | list>
  - Hot areas: <none | list with reasons>

## Testing
<one of:>
  - Recommend: <specific tests to add or modify>
  - Existing coverage sufficient: <brief justification>
  - N/A: <reason, e.g., "documentation-only change">

## Claim
<one of:>
  - Will claim: issue #<n> is open, unclaimed, on upstream
  - Skip: <reason, e.g., "internal-only issue", "already assigned to me">

Options:
  1. Approve (continue to implementation)
  2. Explain (show rationale for this approach)
  3. Decline (request changes)
```

### On Approve

```bash
bd close "$STEP_ID" --continue
```

**If claiming** (plan indicated "Will claim"):
```bash
# Extract upstream issue number from the local issue's external_ref
# See Step 7 for format convention (gh:org/repo#123 or issue:123)
UPSTREAM_ISSUE=$(bd show "$ISSUE_ID" --json | jq -r '.[0].external_ref // empty' | grep -oE '#[0-9]+$|issue:[0-9]+' | grep -oE '[0-9]+')
if [ -n "$UPSTREAM_ISSUE" ]; then
  gh issue comment "$UPSTREAM_ISSUE" --repo "$ORG_REPO" --body "I'd like to work on this. I'll submit a PR soon."
fi
```

Proceed to branch creation.

### On Explain

Present the rationale you prepared internally:

```
## Rationale

**Why this approach:**
<explanation of the chosen solution>

**Alternatives considered:**
<what was rejected and why>

**Tradeoffs:**
<what we're accepting and why it's acceptable>

---
Options:
  1. Approve (continue to implementation)
  2. Decline (request changes)
```

After presenting rationale, wait for approve or decline.

### On Decline

```
What would you like to change about the plan?
```

Stay in plan phase, revise based on feedback. After making changes:
1. Update the plan in the `plan` step bead
2. Re-present the gate-plan checkpoint with updated content
3. Wait for approval again

Do NOT close the gate step until explicitly approved.

---

## Gate 2: `gate-submit` (Pre-Submit Review)

**MANDATORY STOP** - Create draft PR, present for review, wait for explicit user approval before marking ready.

### Variable Recovery (Required After Session Resume)

If resuming at this gate after compaction or new session, recover required variables:

```bash
# Recover ISSUE_ID, MOL_ID, ORG_REPO
source "$SKILL_DIR/resources/scripts/context-recovery.sh"

# Recover DEFAULT_BRANCH (needed for CI check)
DEFAULT_BRANCH=$(gh api repos/$ORG_REPO --jq '.default_branch')
```

### Idempotent Entry (Critical for Session Recovery)

When entering gate-submit, FIRST check if a draft PR already exists:

```bash
source "$SKILL_DIR/resources/scripts/pr-check-idempotent.sh"

# If no PR exists, create draft
if [ -z "$PR_NUMBER" ]; then
  git push -u origin $BRANCH
  gh pr create --repo $ORG_REPO --draft \
    --head "$FORK_OWNER:$BRANCH" \
    --title "<title>" --body "<body>

---
🤖 [Tackled](https://github.com/aleiby/claude-config/tree/master/skills/tackle) with [Claude Code](https://claude.com/claude-code)"
  PR_URL=$(gh pr view --repo $ORG_REPO --json url --jq '.url')
  PR_NUMBER=$(gh pr view --repo $ORG_REPO --json number --jq '.number')
  IS_DRAFT=true

  # Store PR_NUMBER in issue notes for recovery after compaction
  bd update "$ISSUE_ID" --append-notes "pr_number: $PR_NUMBER"
fi
```

This sets: `PR_NUMBER`, `IS_DRAFT`, `PR_URL`, `BRANCH`, `FORK_OWNER`

**Requires**: `ORG_REPO` and `ISSUE_ID` must be set (from set-vars.sh).

**⚠️ REQUIRED PR FOOTER**: Always include the "Tackled with Claude Code" footer shown above. Do NOT use the generic "Generated with Claude Code" or "Created with Claude Code" - those indicate the PR was not created through the tackle workflow.

GitHub is the source of truth for PR state.

### Show to User

```
┌────────────────────────────────────────────────────────────────────┐
│  📤 CHECKPOINT: Pre-Submit Review                                  │
└────────────────────────────────────────────────────────────────────┘

Draft PR for <issue-id>:

## Review on GitHub (DRAFT)
<upstream-pr-url>

## Title
<pr-title>

## Target
<upstream> <- <fork-owner>:<branch-name>

## Summary
<pr-body-preview>

## Changes
<file-list with +/- counts>

## Validation
  - Tests: PASSED
  - Isolation: PASSED (single concern)
  - Rebased: Yes, on upstream default branch

Approve to check CI and mark PR ready for maintainer review.
```

### On Approve

**⚠️ MANDATORY: Wait for CI to complete before marking PR ready.**

Do NOT run `gh pr ready` until CI finishes. Use ci-status-check.sh which polls until complete:

```bash
source "$SKILL_DIR/resources/scripts/ci-status-check.sh"
```

This sets: `FAILED`, `PRE_EXISTING`, `PENDING`

**Requires**: `PR_NUMBER`, `ORG_REPO`, and `DEFAULT_BRANCH` must be set.

The script polls CI every 30 seconds while checks are pending, then checks if any failures are pre-existing on the default branch.

Present CI status to user:
```
CI Status:
  - Passed: <n>
  - Failed: <n> <if pre-existing: "(pre-existing on main)">
  - Skipped: <n>

<if failures are NOT pre-existing>
Options:
  - Fix failures and re-push (returns to implement phase)
  - Submit anyway (maintainer may reject)

<if all failures are pre-existing>
All failures are pre-existing on main. Safe to proceed.
```

**If user chooses "Fix failures":**

Do NOT close gate-submit. Stay at this gate and iterate:

1. Fix the failing check (e.g., run `golangci-lint run ./...` locally, fix issues)
2. Commit the fix: `git commit --amend` (keep single commit) or new commit
3. Force-push: `git push -f origin <branch>`
4. Wait for CI to re-run (poll with `gh pr view $PR_NUMBER --repo $ORG_REPO --json statusCheckRollup`)
5. Re-present the gate-submit checkpoint with updated CI status
6. Repeat until CI passes or user chooses to submit anyway

**If CI passed** (or failures are pre-existing, or user chooses to submit anyway), store PR info and proceed:

```bash
bd update "$STEP_ID" --notes="pr_number: $PR_NUMBER
pr_url: $PR_URL
ci_status: passed
approved_at: $(date -Iseconds)"

bd close "$STEP_ID" --reason "Approved - PR #$PR_NUMBER ready for review" --continue
```

Proceed to submit phase (marks the draft PR as ready for review).

### On Reject

```
What would you like to change before submission?
Options:
  - Modify implementation (will force-push to update draft PR)
  - Update PR title/body (can edit draft PR directly)
  - Add more tests
  - Close draft PR and start over
  - Other changes
```

Return to implement phase for revisions. After making changes:
1. Force-push updated branch: `git push -f origin <branch>`
2. Update draft PR if needed: `gh pr edit $PR_NUMBER --repo $ORG_REPO ...`
3. Re-run validation (tests, linter, isolation)
4. Re-present the gate-submit checkpoint
5. Wait for approval again

Do NOT close the gate step until explicitly approved.

---

## Gate Help

If user asks for help or seems confused at a gate:

```
You're at the <gate-name> gate.

This is a mandatory approval checkpoint. The skill will not proceed
until you explicitly approve or decline.

Respond naturally:
  "yes", "approve", "looks good" -> approve
  "why", "explain", "rationale" -> explain (gate-plan only)
  "no", "wait", "revise"        -> decline
```

## Agent Safety

**Critical for autonomous agents:**

Gates apply to ALL agents equally. No agent can bypass gates. No role-specific exceptions.

If an agent reaches a gate without a human in the loop:
1. Present gate
2. Wait for human approval
3. Do not timeout and auto-approve
4. Do not proceed on any heuristic

---

## Reflect

**⚠️ You are NOT done until this step is complete.** PR submission is not the end of the workflow.

The `reflect` step captures issues with the tackle process itself (not task-specific problems).

**Load REFLECT.md for full instructions.** At minimum, answer these before closing:

1. **Skill issues?** Wrong commands, unclear instructions, missing steps?
2. **Research issues?** Missed existing work, stale data, duplicated effort?
3. **Agent issues?** Needed user correction? Forgot steps? Wrong assumptions?

If any issues found: load REFLECT.md for recording format and pattern detection.

After completing the reflect assessment:

```bash
# 1. Close the reflect step
bd close "$STEP_ID" --reason "Clean run - no issues"  # or "See molecule notes"

# 2. Set squash summary (captures PR outcome for audit trail)
# Include friction summary if issues found (details go in molecule notes per REFLECT.md)
export SQUASH_SUMMARY="PR #123: Added feature X - clean implementation"

# 3. Close molecule and unhook
source "$SKILL_DIR/resources/scripts/complete-tackle.sh"
```

The script squashes the molecule (creating a digest for audit trail), closes it, and unhooks the issue (freeing your hook for other work while the PR awaits review).

**Why squash?** Tackle creates wisps (ephemeral molecules) due to a known limitation in `gt sling --on`. Squashing preserves the audit trail before the wisp disappears.

**OUTPUT THIS BANNER when tackle completes:**

```
✅ TACKLE COMPLETE: <issue-id> → PR #<number>
```

### Resuming (`/tackle --resume [step]`)

Use after compaction, handoff, or session restart to continue an in-progress tackle.

**What it does:**
1. Run the **Resumption Protocol** (see top of this file)
2. Load resource for the specified step (or auto-detect from `gt hook`)
3. Continue execution

See **Resource Loading** section above for step names and their resources.

**When to use:**
- After `/compact`
- After `gt handoff` brings you back
- When starting a new session with work on hook
- When confused about tackle state
- When the formula step says "Run `/tackle --resume <step>`"

### Pausing (`/tackle --pause`)

To temporarily set aside a tackle and work on something else:

```bash
# Get current state for the banner
ISSUE_ID=$(gt hook --json | jq -r '.pinned_bead.id // empty')
STEP_ID=$(gt hook --json | jq -r '.progress.current_step // "unknown"')

# Detach from hook (molecule stays attached to issue)
gt unsling --force
```

**OUTPUT THIS BANNER when tackle is paused:**

```
⏸️ TACKLE PAUSED: <issue-id> at step: <step-id>

Resume later with: /tackle <issue-id>
```

The molecule and all progress remain attached to the issue. Resume later with:
```bash
/tackle <issue-id>  # Auto-hooks and resumes from where you left off
```

**Use this when:** Switching to higher-priority work, comparing approaches, or taking a break.

### Aborting (`/tackle --abort`)

**⚠️ DESTRUCTIVE**: This permanently destroys the molecule. You cannot resume after aborting.

To abandon a tackle mid-workflow:

1. **Burn the molecule** (discard without squashing):
   ```bash
   bd --no-daemon mol burn <molecule-id> --force
   ```

2. **Clean up branch** (if created):
   ```bash
   git checkout main  # or default branch
   git branch -D <tackle-branch>
   ```

3. **Update issue** (optional):
   ```bash
   bd update "$ISSUE_ID" --status=open --notes="Tackle aborted"
   ```

The issue returns to ready state for a **fresh** tackle (no prior progress).

**Use this when:** The approach was wrong, requirements changed, or you want to start over.

**OUTPUT THIS BANNER when tackle is aborted:**

```
⛔ TACKLE ABORTED: <issue-id>
```

## Session Handoff

When handing off mid-tackle, include this context for the next session:

### Handoff Message Should Include

```markdown
## Tackle Status: <issue-id>

Molecule: <molecule-id>
Current step: <step-name> (from gt hook)
Branch: <branch-name>

### Completed
- [x] plan (approved)
- [ ] implement (in progress)

### Key State
- Draft PR: #<number> (if created)
- PR URL: <url>
- Gate approvals: plan ok, submit pending

### Next Action
<what the next session should do>
```

### Resuming After Handoff

Run `/tackle --resume` - it handles molecule re-attachment and state recovery.
