# Reflect Phase

Reflect on what went wrong with the tackle process and improve the skill.

## Purpose

This step runs **immediately after PR submission** (not after merge). Capture friction and errors while fresh.

**CRITICAL**: The reflect step is how tackle learns and improves. Skipping evaluation or writing "Clean run" without review loses valuable learning data. Take this step seriously.

## Your Feedback is Valuable

**Don't hold back.** Every issue you report helps improve tackle for future runs. There's no blame here - we want to know:

- What confused you, even briefly
- Where you hesitated or felt uncertain
- Commands that didn't work as expected
- Steps that felt unnecessary or out of order
- Anything you did differently from the instructions

**"Clean run" should be rare.** Most tackles have at least some micro-friction worth noting. If you're writing "Clean run" frequently, you're probably not reflecting deeply enough.

---

## Reflect Checklist (EVALUATE BEFORE CLOSING)

**Do not write "Clean run" until you've reviewed each category:**

### 1. Skill/Formula Issues?
- Were any instructions wrong or unclear?
- Did any commands fail due to wrong flags?
- Were steps missing or in wrong order?
- Did gates work correctly?

### 2. Research Issues?
- Did we miss existing work (closed issues, open PRs)?
- Was upstream research stale or incomplete?
- Did we duplicate someone else's effort?

### 3. Agent Behavior Issues?
- Did I jump to conclusions without investigating?
- Did I propose a fix that turned out to be wrong?
- Did I forget any steps?
- Did I need user correction?

### 4. Molecule Cleanup?
- Are ALL steps closed (not just reflect)?
- Is the ROOT MOLECULE closed?
- Did I record issues in **issue notes** for pattern detection?

### 5. Off-Script Moments?
**This is critical for improving guardrails.** Think back through your session:

- Did you skip any steps? Which ones and why?
- Did you do steps in a different order? Why did that seem better?
- Did you run commands not in the instructions? What were they?
- Did you improvise a workaround? What problem were you solving?
- Did you ignore any guidance? What made you decide to deviate?

**Be specific.** Instead of "I skipped the cache check", write:
> "Skipped cache-freshness.sh at line 42 because ORG_REPO wasn't set and I didn't know I needed to run detect-upstream.sh first. Improvised by running gh api directly."

### 6. Improvement Ideas?
Based on your experience with this tackle, what would make future runs smoother?

- What information did you wish you had earlier?
- What steps felt redundant or could be combined?
- What guardrails would have prevented mistakes you made?
- What automation would have saved time?
- What error messages were unhelpful?

**Even small suggestions matter.** "The IMPLEMENT.md could mention that go generate is needed before build" is valuable feedback.

**Only write "Clean run - no issues" if you've reviewed ALL categories and found nothing.**

---

## What to Log

**IMPORTANT**: Only log issues that tackle could help prevent in future runs.

### IN SCOPE: Tackle skill issues
- Command failures due to wrong flags in instructions
- Missing `--no-daemon` or other required flags
- Confusing workflow steps or unclear instructions
- Missing guidance that applies to ALL tackle runs
- State management issues (handoff, molecule attachment)
- Gate workflow problems

### IN SCOPE: Systemic issues tackle could address
- Working in wrong directory/git clone
- Forgetting to check for existing work before starting
- Common agent mistakes that guardrails could prevent
- Environment assumptions that should be verified

### OUT OF SCOPE (task-specific issues)
- Test failures in the code being submitted
- Upstream codebase quirks or conventions
- Merge conflicts or rebasing issues
- PR review feedback about the code

**Rule of thumb**: Could tackle reasonably add guidance/checks to prevent this? If yes, log it. If it's inherent to the specific task, don't.

## Pattern Detection via Molecule History

Tackle molecules are labeled `formula:tackle` for querying. Molecules with friction are also labeled `tackle:friction`. Use past molecules to detect patterns:

```bash
source "$SKILL_DIR/resources/scripts/query-friction.sh"
# Or run directly: bash "$SKILL_DIR/resources/scripts/query-friction.sh"
```

Check issue notes for recurring friction before proposing fixes.

## When to Fix

### Report Immediately (no pattern needed)
Objective errors that will always fail:
- Wrong command flags (`--silent` doesn't exist)
- Missing required flags (`--no-daemon` required but not in instructions)
- Syntax errors in example commands
- Incorrect command names or paths

Predictable inefficiencies that will always waste effort:
- Design flaws that cause redundant work every run
- Missing state tracking that forces unnecessary re-fetches
- Logic errors that produce correct but wasteful behavior

These are bugs or design flaws, not patterns. **Do NOT edit skill files yourself.**
Instead:
1. Record the friction on the **issue** (see Recording Issues below)
2. Mail the mayor with the proposed fix:
```bash
STEP="reflect" ERROR_DESC="Objective skill bug: <description>" \
  source "$SKILL_DIR/resources/scripts/report-problem.sh"
```
The mayor will triage and fix the skill.

### Note and Check for Patterns (2+ occurrences)
Subjective issues that need validation:
- "Instructions were confusing" - might be context-specific
- "Would be nice to have X" - suggestions need confirmation
- "Step took multiple attempts" - might be user error

**Rules:**
- 1 occurrence: Note in issue notes, wait for pattern
- 2+ occurrences: Propose fix
- 3+ occurrences: Definitely fix

## Recording Issues

When there are issues, record them in the **issue notes** (not molecule or step). This ensures friction data survives molecule GC and is queryable for pattern detection.

**Use this comprehensive format:**

```bash
# Add friction to ISSUE notes (ISSUE_ID from context-recovery.sh)
bd update "$ISSUE_ID" --append-notes "$(cat <<'EOF'
=== TACKLE FEEDBACK ===

ERRORS (commands/instructions that failed):
- <command that failed>: <what happened> → <what worked instead>

FRICTION (things that slowed you down):
- <step/resource>: <what was confusing or inefficient>

OFF-SCRIPT (deviations from instructions):
- <what you did differently>: <why you deviated>
- Skipped: <step> because <reason>
- Added: <step> because <needed for this task>

SUGGESTIONS (improvements for future tackles):
- <specific actionable suggestion>
- <another suggestion>

WHAT WORKED WELL:
- <steps that were clear and helpful>
EOF
)"

# Add friction label to ISSUE for querying
bd update "$ISSUE_ID" --add-label "tackle:friction"
```

**Tips for good feedback:**
- Be specific: "line 42 of IMPLEMENT.md" not "the implement step"
- Include context: why did you deviate, what were you trying to do?
- Suggest fixes: don't just report problems, propose solutions
- Note severity: was it a blocker or just annoying?

This becomes queryable history for pattern detection. Issues are permanent; molecules are ephemeral wisps that may be GC'd.

## Proposing Skill Improvements

For persistent problems (2+ occurrences across molecules), propose changes:

```
## Tackle Skill Improvement

Issue: <description of persistent problem>
Occurrences: Found in molecules <list>
Affected resource: <RESEARCH.md | IMPLEMENT.md | etc.>

Signal: "<exact error or friction point>"

Current text:
> existing instruction

Proposed text:
> improved instruction

Rationale: <why this helps>
```

Present for review. Only apply with explicit approval.

## Completing Reflect

### If the run was smooth

```bash
# Close reflect step
bd close <reflect-step-id> --reason "Clean run - no issues"

# Set squash summary and complete
export SQUASH_SUMMARY="PR #<number>: <brief description> - clean run"
source "$SKILL_DIR/resources/scripts/complete-tackle.sh"
```

### If there were issues

First record friction in issue notes (see Recording Issues above), then:

```bash
# Close reflect step
bd close <reflect-step-id> --reason "See issue notes for friction details"

# Set squash summary with friction summary
export SQUASH_SUMMARY="PR #<number>: <brief description> - friction: <1-line summary>"
source "$SKILL_DIR/resources/scripts/complete-tackle.sh"
```

### What complete-tackle.sh Does

The script:
1. **Squashes the molecule** - Creates a digest with SQUASH_SUMMARY for audit trail
2. **Closes the root molecule** - Marks work complete
3. **Unhooks the issue** - Frees your hook for other work

**Why squash?** Tackle creates wisps (ephemeral molecules) due to a limitation in `gt sling --on`. Squashing preserves the audit trail before wisps disappear.

**Why this matters**: Open molecules pollute future queries. Pattern detection depends on issues with friction recorded in notes and `tackle:friction` labels.

## Example

```
## Tackle Reflect: gt-mol-xxxxx

Reviewed tackle process for worktree health check PR.

### Checklist Review

1. **Skill Issues**: Yes - see errors below
2. **Research Issues**: No - found existing work correctly
3. **Agent Behavior**: Yes - jumped ahead without reading all instructions
4. **Molecule Cleanup**: All steps closed ✓
5. **Off-Script Moments**: Yes - see below
6. **Improvement Ideas**: Yes - see suggestions

### Errors

1. **ERROR**: `cache-freshness.sh` failed with "ORG_REPO must be set"
   - Line 24 of cache-freshness.sh expects ORG_REPO
   - Had to figure out I needed to run detect-upstream.sh first
   - Workaround: ran `source detect-upstream.sh` manually
   - Suggestion: cache-freshness.sh should auto-source its dependencies

### Friction

1. **FRICTION**: PROJECT-RESEARCH sub-agent took 2+ minutes
   - Many failed bd commands with jq quoting issues
   - Eventually worked but burned lots of context
   - Severity: Annoying, not blocking

### Off-Script Moments

1. **Skipped**: Gate-plan approval wait
   - Why: User had already approved verbally in earlier message
   - Impact: None, but technically deviated from workflow

2. **Added**: Manual `git fetch upstream` before branch creation
   - Why: IMPLEMENT.md doesn't mention this but it's needed for fresh upstream ref
   - Suggestion: Add to step 1 of IMPLEMENT.md

3. **Improvised**: Ran `bd list --json | jq ...` instead of suggested command
   - Why: The suggested jq pattern `!= null` caused bash escaping issues
   - Workaround: Used truthy check `select(.field)` instead

### Suggestions

1. Add script dependency documentation to each script header
2. IMPLEMENT.md should mention `git fetch upstream` in branch setup
3. Add jq quoting tips to sub-agent resources (bash `!` expansion)
4. Consider combining detect-upstream.sh + cache-freshness.sh

### What Worked Well

- Gate checkpoints caught my rushed PR description
- Research sub-agents found related PRs correctly
- Validation step caught missing tests

### Pattern Check
Queried closed tackle molecules for similar issues.
Found 1 prior occurrence of cache-freshness dependency confusion.

### Actions
- Recording feedback in issue notes
- Proposing cache-freshness.sh auto-source fix (2nd occurrence)
```
