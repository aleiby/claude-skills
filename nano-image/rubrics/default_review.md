# Default Image Review Rubric

Score each dimension: PASS / FAIL

## Dimensions

1. **Task adherence** — Does the image match what was requested?
2. **Subject accuracy** — Is the main subject correct and recognizable?
3. **Composition** — Is the layout/arrangement effective?
4. **Style match** — Does it match the intended aesthetic?
5. **Text correctness** — If text was requested, is it legible and spelled correctly?
6. **Artifacts** — Are there obvious visual problems (extra limbs, distortion, blending errors)?

## Decision

| Result | Condition |
|--------|-----------|
| **ACCEPT** | All dimensions PASS, or minor issues user won't care about |
| **RETRY_FAST** | 1-2 dimensions FAIL, issues are fixable with tighter prompt |
| **RETRY_PRO** | Fast retries exhausted, or failure requires better model reasoning |
| **FAIL** | Fundamental mismatch — reclassify request or ask user for clarification |

## Retry budget

- Up to 2 fast retries
- Then escalate to pro
- Up to 2 pro retries
- After that, present best result and ask user
