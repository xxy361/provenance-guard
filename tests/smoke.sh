#!/usr/bin/env bash
# Smoke test for the Provenance Guard API — submits a spread of texts and
# prints the classification for each.
#
# Usage:  ./tests/smoke.sh            # defaults to http://localhost:5001
#         BASE=http://localhost:8000 ./tests/smoke.sh
#
# Note: macOS AirPlay Receiver squats on port 5000, so run Flask elsewhere
# (e.g. `flask --app app run --port 5001`) and point BASE at it.

set -euo pipefail
BASE="${BASE:-http://localhost:5001}"

# Parallel arrays: a label for each case and the text to submit.
labels=(
  "Clearly AI-generated (should score high)"
  "Clearly human-written (should score low)"
  "Borderline: formal human writing (may score mid-high on stylometrics)"
  "Borderline: lightly edited AI output (should ideally score mid-range)"
)

texts=(
  "Artificial intelligence represents a transformative paradigm shift in modern society. It is important to note that while the benefits of AI are numerous, it is equally essential to consider the ethical implications. Furthermore, stakeholders across various sectors must collaborate to ensure responsible deployment."

  "ok so i finally tried that new ramen place downtown and honestly? underwhelming. the broth was fine but they put WAY too much sodium in it and i was thirsty for like three hours after. my friend got the spicy version and said it was better. probably won't go back unless someone drags me there"

  "The relationship between monetary policy and asset price inflation has been extensively studied in the literature. Central banks face a fundamental tension between their mandate for price stability and the unintended consequences of prolonged low interest rates on equity and real estate valuations."

  "I've been thinking a lot about remote work lately. There are genuine tradeoffs — flexibility and no commute on one side, isolation and blurred work-life boundaries on the other. Studies show productivity varies widely by individual and role type."
)

for i in "${!texts[@]}"; do
  echo "== [$i] ${labels[$i]} =="
  # jq -Rs safely JSON-encodes the text (quotes, newlines, etc.).
  payload=$(jq -n --arg t "${texts[$i]}" --arg c "tester" '{text: $t, creator_id: $c}')
  curl -s -X POST "$BASE/submit" \
    -H "Content-Type: application/json" \
    -d "$payload" | python3 -m json.tool
  echo
done