#!/usr/bin/env bash

set -euo pipefail

ts() {
  date "+%Y-%m-%d %H:%M:%S"
}

echo "[$(ts)] Getting project list..."
PROJECTS=$(gcloud projects list --format="value(projectId)")

echo "[$(ts)] Getting region list..."
REGIONS=$(gcloud compute regions list --format="value(name)")

echo "[$(ts)] Getting auth token..."
TOKEN=$(gcloud auth print-access-token)

OUT="vertex_model_counts.csv"
echo "project_id,region,count" > "$OUT"

echo "[$(ts)] Starting scan..."

for PROJECT in $PROJECTS; do
  echo "[$(ts)] Project: $PROJECT"

  TOTAL=0

  for REGION in $REGIONS; do
    echo "[$(ts)]   Region: $REGION"

    NEXT=""
    COUNT=0

    while true; do
      if [[ -z "$NEXT" ]]; then
        URL="https://${REGION}-aiplatform.googleapis.com/v1/projects/${PROJECT}/locations/${REGION}/models"
      else
        URL="https://${REGION}-aiplatform.googleapis.com/v1/projects/${PROJECT}/locations/${REGION}/models?pageToken=${NEXT}"
      fi

      RESP=$(curl -s -H "Authorization: Bearer $TOKEN" -H "Content-Type: application/json" "$URL" || true)

      # Some regions return HTML or empty output, skip those
      if ! echo "$RESP" | jq empty >/dev/null 2>&1; then
        echo "$PROJECT,$REGION,0" >> "$OUT"
        echo "[$(ts)]     → 0 (region not supported)"
        break
      fi

      PAGE=$(echo "$RESP" | jq '.models | length // 0')
      COUNT=$((COUNT + PAGE))

      NEXT=$(echo "$RESP" | jq -r '.nextPageToken // ""')
      [[ -z "$NEXT" ]] && break
    done

    echo "$PROJECT,$REGION,$COUNT" >> "$OUT"
    echo "[$(ts)]     → $COUNT"
    TOTAL=$((TOTAL + COUNT))
  done

  echo "[$(ts)] Project $PROJECT total: $TOTAL"
done

echo "[$(ts)] Done. Output written to $OUT"
