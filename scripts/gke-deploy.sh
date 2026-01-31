#!/usr/bin/env bash
set -euo pipefail

: "${PROJECT_ID:?Set PROJECT_ID}"
: "${REGION:?Set REGION (e.g. europe-west1)}"
: "${CLUSTER:?Set CLUSTER name}"
: "${REPO:?Set REPO (Artifact Registry repo name)}"
: "${IMAGE_TAG:=latest}"
: "${NAMESPACE:=ragstar}"
: "${RAGSTAR_OLLAMA_URL:?Set RAGSTAR_OLLAMA_URL}"
: "${RAGSTAR_OLLAMA_API_KEY:?Set RAGSTAR_OLLAMA_API_KEY}"
: "${RAGSTAR_ADMIN_TOKEN:?Set RAGSTAR_ADMIN_TOKEN}"

IMAGE="${REGION}-docker.pkg.dev/${PROJECT_ID}/${REPO}/ragstar:${IMAGE_TAG}"

# Configure project and cluster access

gcloud config set project "${PROJECT_ID}"

gcloud container clusters get-credentials "${CLUSTER}" --region "${REGION}"

# Namespace

kubectl apply -f deploy/gke/namespace.yaml

# Secrets (no plaintext file committed)

kubectl -n "${NAMESPACE}" create secret generic ragstar-secrets \
  --from-literal=RAGSTAR_OLLAMA_URL="${RAGSTAR_OLLAMA_URL}" \
  --from-literal=RAGSTAR_OLLAMA_API_KEY="${RAGSTAR_OLLAMA_API_KEY}" \
  --from-literal=RAGSTAR_ADMIN_TOKEN="${RAGSTAR_ADMIN_TOKEN}" \
  ${RAGSTAR_GITHUB_TOKEN:+--from-literal=RAGSTAR_GITHUB_TOKEN="${RAGSTAR_GITHUB_TOKEN}"} \
  --dry-run=client -o yaml | kubectl apply -f -

# Storage

kubectl apply -f deploy/gke/pvc.yaml

# Deployment + Service

sed "s|IMAGE_PLACEHOLDER|${IMAGE}|g" deploy/gke/deployment.yaml | kubectl apply -f -

kubectl apply -f deploy/gke/service.yaml

echo "Deployed: ${IMAGE}"
