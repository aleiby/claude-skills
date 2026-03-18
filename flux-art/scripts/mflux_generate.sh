#!/bin/bash
# Wrapper around mflux-generate-flux2 that creates proper .meta.json sidecars
# for the gallery server. Run via: mac bash /path/to/mflux_generate.sh [args...]
#
# Usage: mac bash ~/.claude/skills/flux-art/scripts/mflux_generate.sh \
#   --model flux2-klein-4b --quantize 8 \
#   --prompt "..." --width 1024 --height 576 --steps 4 \
#   --output /Users/aleiby/projects/signal-line/nano-image-output/my-image.png

source ~/.zshrc 2>/dev/null

# Parse args to extract values we need for metadata
MODEL=""
QUANTIZE=""
PROMPT=""
OUTPUT=""
WIDTH=""
HEIGHT=""
STEPS=""
GUIDANCE=""

ARGS=("$@")
for ((i=0; i<${#ARGS[@]}; i++)); do
  case "${ARGS[$i]}" in
    --model|-m) MODEL="${ARGS[$((i+1))]}" ;;
    --quantize|-q) QUANTIZE="${ARGS[$((i+1))]}" ;;
    --prompt) PROMPT="${ARGS[$((i+1))]}" ;;
    --output) OUTPUT="${ARGS[$((i+1))]}" ;;
    --width) WIDTH="${ARGS[$((i+1))]}" ;;
    --height) HEIGHT="${ARGS[$((i+1))]}" ;;
    --steps) STEPS="${ARGS[$((i+1))]}" ;;
    --guidance) GUIDANCE="${ARGS[$((i+1))]}" ;;
  esac
done

# Run mflux
START=$(date +%s)
mflux-generate-flux2 "$@"
EXIT_CODE=$?
END=$(date +%s)
ELAPSED=$((END - START))

if [ $EXIT_CODE -ne 0 ]; then
  exit $EXIT_CODE
fi

# Build model name
MODEL_NAME="${MODEL}"
if [ -n "$QUANTIZE" ]; then
  MODEL_NAME="${MODEL_NAME}-q${QUANTIZE}"
fi
MODEL_NAME="${MODEL_NAME}-local-mac"

# Write .meta.json sidecar
if [ -n "$OUTPUT" ] && [ -f "$OUTPUT" ]; then
  META="${OUTPUT}.meta.json"
  FILE_SIZE=$(stat -f%z "$OUTPUT" 2>/dev/null || stat -c%s "$OUTPUT" 2>/dev/null)
  TIMESTAMP=$(date -u +"%Y-%m-%dT%H:%M:%SZ")

  cat > "$META" <<EOF
{
  "model": "${MODEL_NAME}",
  "model_tier": "flux",
  "endpoint": "local:mflux-mac",
  "prompt": $(python3 -c "import json; print(json.dumps('''${PROMPT}'''))" 2>/dev/null || echo "\"${PROMPT}\""),
  "image_size": "${WIDTH}x${HEIGHT}",
  "num_inference_steps": ${STEPS:-4},
  "guidance_scale": ${GUIDANCE:-1.0},
  "quantize": ${QUANTIZE:-null},
  "output_file": "${OUTPUT}",
  "file_size_bytes": ${FILE_SIZE:-0},
  "image_width": ${WIDTH:-1024},
  "image_height": ${HEIGHT:-576},
  "inference_time": ${ELAPSED},
  "timestamp": "${TIMESTAMP}"
}
EOF
  echo "Metadata written to: ${META}"
fi
