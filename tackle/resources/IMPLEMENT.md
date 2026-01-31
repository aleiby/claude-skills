# Implementation Phase

Covers: plan creation, branch setup, and code implementation.

## Plan Phase

Create an implementation plan based on:
- Issue requirements
- Upstream context (from cached research)
- Cached research (patterns, conventions)

### Check: Upstream Issue Required?

From cached research, check if upstream requires an issue first:
```yaml
guidelines:
  requires_issue_first:
    - "Larger changes"
    - "New features"
```

If this change qualifies as "larger" (significant new feature, architectural change, etc.):
1. Check if a related upstream issue already exists (from pre-molecule research)
2. If not, consider creating one first: `gh issue create --repo <upstream>`
3. Reference the upstream issue in the PR

For small bug fixes, docs, or focused changes - proceed without upstream issue.

### Plan Structure

```markdown
## Implementation Plan for <issue-id>

### Goal
<What we're fixing/implementing>

### Files to Modify
- `path/to/file1` - <what changes>
- `path/to/file2` - <what changes>

### Tests (TDD)
<Required for new functionality where project has test infrastructure>
- Test file: `path/to/file_test`
- Test cases:
  - <Test case 1 - what it verifies>
  - <Test case 2 - what it verifies>
- For bug fixes: regression test proving the bug is fixed
- For features: unit tests demonstrating the feature works

### Approach
<Step-by-step implementation approach>

### Upstream Alignment
- Following pattern from: <recent PR or file>
- Commit style: <per guidelines>
- Test approach: <per guidelines>

### Risks
- <Any potential issues>
- <Hot areas to be careful with>
```

**Note**: Skip Tests section only when:
- Project has no test infrastructure
- Change is purely documentation
- Change is trivial config that upstream doesn't test

### Update Molecule

```yaml
phase: "gate-plan"
plan:
  goal: "<goal>"
  files:
    - path: "path/to/file.go"
      changes: "description"
  approach: "<approach>"
```

Then **STOP** - proceed to gate-plan (see SKILL.md).

## Working Directory

**IMPORTANT**: Work in YOUR rig - the directory you were spawned in.

```bash
pwd  # Verify you're in your own rig before making changes
```

Don't edit files in other agents' directories. If unsure about the directory structure, consult https://github.com/steveyegge/gastown/blob/main/docs/design/architecture.md#directory-structure

## Branch Phase

After plan approval, create clean branch from upstream.

### ⚠️ Branch Strategy Warning

**NEVER sync or merge `main` with `upstream/main`.**

The `main` branch may be pinned to a specific upstream tag with local patches applied. It is NOT meant to track upstream HEAD.

| Branch | Purpose | Base |
|--------|---------|------|
| `main` | Local build with patches | `upstream/main@tag` + cherry-picks |
| `test-*` | Temporary test branches | `main` |
| `fix/*`, `feat/*` | PR branches (clean) | `upstream/main@HEAD` |

- **PR branches**: Always create from `upstream/main` (clean for submission)
- **Test branches**: Create from `main` for testing with local patches
- **main branch**: DO NOT modify - managed separately

If you notice `main` is "behind" upstream, that is intentional. Do not attempt to update it.

### Fetch Latest

```bash
git fetch $UPSTREAM_REMOTE
```

### Create Branch

Use upstream and default branch (see SKILL.md "Detect Upstream"):

```bash
git checkout -b <type>/<issue-id>-<description> $UPSTREAM_REF
```

Branch naming: `<type>/<issue-id>-<short-description>`

**Issue ID preference:** Use upstream issue number (e.g., `123`) if available, otherwise fall back to local beads ID (e.g., `hq-1234`). Upstream issue numbers are more meaningful in the PR context.

Types:
- `fix/` - Bug fixes
- `feat/` - New features
- `docs/` - Documentation
- `refactor/` - Refactoring
- `test/` - Test additions

Examples:
```bash
# With upstream issue
git checkout -b fix/123-doctor-indent upstream/main

# Without upstream issue (local beads ID)
git checkout -b fix/hq-1234-doctor-indent upstream/main
```

### Update Molecule

```yaml
phase: "implement"
branch: "fix/hq-1234-doctor-indent"
branch_base: "upstream/main"
```

## Implement Phase

Follow test-driven development (TDD) workflow.

### Testing with Local Patches

If the project requires building, test on a temporary branch from `main`:

`$BUILD_CMD` and `$TEST_CMD` are set by `set-vars.sh` from cached project research.
If empty, detect from project files (go.mod → go, package.json → npm, Cargo.toml → cargo, pyproject.toml → python).

```bash
source "$SKILL_DIR/resources/scripts/set-vars.sh"

# Save current PR branch
PR_BRANCH=$(git branch --show-current)

# Create temp test branch from main (has local patches)
git checkout -b test-wip main
git cherry-pick $PR_BRANCH  # or cherry-pick specific commits

# Build and test
$BUILD_CMD && $TEST_CMD

# Return to PR branch, delete temp
git checkout $PR_BRANCH
git branch -D test-wip
```

Repeat this cycle for each test iteration. The temp branch is always fresh.

### Step 1: Write Tests First

If tests were planned (see Plan Structure above):

1. **Write the test cases** from your plan (on PR branch)
2. **Run tests - verify they FAIL**
   - Create temp test branch, cherry-pick, build, run tests
   - Tests should fail because the feature/fix doesn't exist yet
   - If tests pass, either the issue is already fixed or tests are wrong
3. **Commit the failing tests** (optional, some prefer single commit)

```bash
# On PR branch: write tests, commit
git commit -m "test(scope): add tests for feature (red phase)"

# Create temp branch to verify tests fail
git checkout -b test-wip main
git cherry-pick fix/123-something
$BUILD_CMD && $TEST_CMD
# Expected: FAIL

# Back to PR branch
git checkout fix/123-something
git branch -D test-wip
```

### Step 2: Implement to Make Tests Pass

Write the minimum code needed to make tests pass:

1. **Implement the fix/feature** (on PR branch)
2. **Run tests - verify they PASS** (on temp test branch)
3. **Commit the implementation**

```bash
# On PR branch: implement, commit
git commit -m "fix(scope): implement feature (#123)"

# Create temp branch to verify tests pass
git checkout -b test-wip main
git cherry-pick fix/123-something~1..fix/123-something  # cherry-pick range
$BUILD_CMD && $TEST_CMD
# Expected: PASS

# Back to PR branch
git checkout fix/123-something
git branch -D test-wip
```

### Guidelines

1. **Follow cached research**:
   - Use detected formatter (`gofmt`, `prettier`, etc.)
   - Follow commit message format
   - Match coding style

2. **Atomic commits**:
   - Each commit should be a logical unit
   - Conventional commit messages: `type(scope): description`
   - Reference issue (prefer upstream issue number if available):
     - With upstream issue: `fix(doctor): correct indentation (#123)`
     - Without upstream issue: `fix(doctor): correct indentation (hq-1234)`

3. **No tracking references in code**:
   - NEVER add bead IDs, GitHub issue numbers, PR references, or tackle skill references in code comments
   - No `// Fixed in #123`, `// See hq-1234`, `// PR #456`, `// Tackled`, etc.
   - Code comments should explain *why*, not reference external tracking systems
   - Tracking references belong in commit messages and PR descriptions only
   - **Exception**: The "Tackled" footer in PR descriptions is required (see SUBMIT.md)

4. **Stay focused**:
   - Only change what's needed for the issue
   - Don't fix unrelated things
   - Don't refactor beyond scope
   - Don't add features not requested

4. **Don't break existing tests**:
   - Run full test suite before considering implementation complete
   - Fix any regressions introduced

### Commit Format

From cached research (stored in cache bead description, see PROJECT-RESEARCH sub-agent output):
```yaml
commits:
  tense: "present"
  subject_max_length: 72
  issue_reference_format: "(#xxx)"  # or "(hq-xxx)" if no upstream issue
```

Examples:
```bash
# With upstream issue number (preferred)
git commit -m "fix(doctor): correct indentation in database check (#123)"

# Without upstream issue (fallback to local beads ID)
git commit -m "fix(doctor): correct indentation in database check (hq-1234)"
```

### Progress Updates

During implementation, update molecule with progress:
```yaml
phase: "implement"
commits:
  - hash: "abc1234"
    message: "fix(doctor): correct indentation"
  - hash: "def5678"
    message: "test(doctor): add indentation test"
```

### Completion

When implementation is complete:
1. Ensure all changes are committed
2. Run quick local test
3. Update molecule: `phase: "validate"`
4. Proceed to validation phase

## Isolation Principle

**Critical**: Each PR should address ONE concern.

Before completing implementation, verify:
- [ ] All changes relate to the issue
- [ ] No unrelated fixes snuck in
- [ ] No drive-by refactoring
- [ ] Commit history is clean and focused

If you noticed other issues while implementing:
- Create new beads issues for them
- Do NOT fix them in this PR
- Note them for future work

```bash
# Create separate issue for discovered problems
bd create --title "Fix unrelated thing noticed during hq-1234" --type task
```
