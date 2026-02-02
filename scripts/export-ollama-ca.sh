#!/usr/bin/env bash
set -euo pipefail

: "${CADDY_VOLUME:=ragstar_caddy-data}"
: "${OUT:=ollama-ca.crt}"

if ! docker volume inspect "${CADDY_VOLUME}" >/dev/null 2>&1; then
  echo "Caddy volume not found: ${CADDY_VOLUME}" >&2
  echo "Set CADDY_VOLUME to the correct docker volume name." >&2
  exit 1
fi

tmp="$(mktemp)"
trap 'rm -f "${tmp}"' EXIT

docker run --rm -v "${CADDY_VOLUME}:/data" alpine:3.20 \
  cat /data/caddy/pki/authorities/local/root.crt > "${tmp}"

mv "${tmp}" "${OUT}"
trap - EXIT

echo "Wrote ${OUT}"
echo "Update the OLLAMA_CA_CRT GitHub secret and re-deploy to sync GKE."
