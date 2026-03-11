# Diagram Review Rubric

Score each dimension: PASS / FAIL

## Dimensions

1. **Structure accuracy** — Does the diagram show the correct relationships/flow?
2. **Label legibility** — All text labels are readable and correctly spelled?
3. **Flow direction** — Clear directional flow (top-down, left-right, or radial)?
4. **Node consistency** — Shapes and sizes are uniform for same-type elements?
5. **Connection clarity** — Lines/arrows don't cross unnecessarily, endpoints are clear?
6. **Visual cleanliness** — No clutter, decorative noise, or unnecessary elements?
7. **Information density** — Right amount of content (not too sparse, not overcrowded)?

## Decision

| Result | Condition |
|--------|-----------|
| **ACCEPT** | Structure correct and labels legible |
| **RETRY_FAST** | Structure close but labels unreadable or flow direction unclear |
| **RETRY_PRO** | Structure fundamentally wrong, or too many crossing lines |
| **FAIL** | Not a diagram at all — reclassify request |

## Diagram-Specific Notes

- Text in diagrams is the #1 failure mode. Escalate to pro early if text matters.
- Prefer simple flat style — photorealistic diagram attempts usually fail.
- Keep node count to 7-10 for best results. More nodes = more likely to need pro.
