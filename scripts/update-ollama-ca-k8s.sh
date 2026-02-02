#!/usr/bin/env bash
set -euo pipefail

: "${CADDY_VOLUME:=ragstar_caddy-data}"
: "${OUT:=ollama-ca.crt}"
: "${NAMESPACE:=ragstar}"
: "${SECRET:=ollama-ca}"
: "${DEPLOYMENT:=ragstar}"

if ! command -v kubectl >/dev/null 2>&1; then
  echo "kubectl is required on PATH." >&2
  exit 1
fi

scripts/export-ollama-ca.sh

kubectl -n "${NAMESPACE}" create secret generic "${SECRET}" \
  --from-file=ollama-ca.crt="${OUT}" \
  --dry-run=client -o yaml | kubectl apply -f -

kubectl -n "${NAMESPACE}" rollout restart "deployment/${DEPLOYMENT}"

echo "Updated ${SECRET} and restarted ${DEPLOYMENT} in ${NAMESPACE}."
