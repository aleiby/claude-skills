# Game Art Review Rubric

Score each dimension: PASS / FAIL

## Dimensions

1. **Aesthetic quality** — Does it read as polished concept art?
2. **Style coherence** — Does it match the requested aesthetic (dieselpunk, painterly, etc.)?
3. **Composition** — Is the layout effective? Strong focal point, balanced elements?
4. **Lighting & atmosphere** — Are light sources dramatic, purposeful, atmospheric?
5. **Structure preservation** (restyle only) — Does the output maintain the original scene composition?
6. **Prompt adherence** — Does it match what was requested? Correct subject, setting, mood?

## Decision

| Result | Condition |
|--------|-----------|
| **ACCEPT** | All dimensions PASS, or minor issues user won't notice |
| **RETRY** | 1-3 dimensions FAIL, fixable with tighter prompt |
| **FAIL** | Fundamental mismatch — reclassify request or ask user |

## Retry strategy

- Up to 3 retries with revised prompt
- Each retry: strengthen positive descriptors, add specificity
- After 3: present best result and ask user

## Prompt revision rules (Flux-specific)

Flux uses **positive-only prompting**. Never add negated terms.

- Strengthen style words: "painterly" → "richly textured painterly brushwork with visible strokes"
- Add lighting specificity: "dramatic lighting" → "warm golden key light from upper left with cool #5B8FA8 teal fill"
- Add material detail: "metal" → "brushed #2B3A42 steel with rivet lines and oil patina"
- Use hex codes for color precision: "warm tones" → "warm #C4842D amber tones with #D4A843 gold accents"
- Add atmosphere: "foggy" → "dense volumetric fog with forward-scattered light shafts"
