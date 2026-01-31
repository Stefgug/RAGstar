#!/usr/bin/env bash
set -euo pipefail

: "${PROJECT_ID:?Set PROJECT_ID}"
: "${REGION:?Set REGION (e.g. europe-west1)}"
: "${REPO:?Set REPO (Artifact Registry repo name)}"
: "${IMAGE_TAG:=latest}"

IMAGE="${REGION}-docker.pkg.dev/${PROJECT_ID}/${REPO}/ragstar:${IMAGE_TAG}"

# Configure Docker to use Artifact Registry

gcloud config set project "${PROJECT_ID}"

gcloud auth configure-docker "${REGION}-docker.pkg.dev" --quiet

# Create repo if missing (requires billing + Artifact Registry API enabled)
if ! gcloud artifacts repositories describe "${REPO}" --location "${REGION}" >/dev/null 2>&1; then
  gcloud artifacts repositories create "${REPO}" \
    --repository-format=docker \
    --location="${REGION}" \
    --description="Ragstar images"
fi

# Build and push

docker build -t "${IMAGE}" .

docker push "${IMAGE}"

echo "Pushed: ${IMAGE}"
