#!/bin/bash
set -euo pipefail

# Lean multi-stage build with BuildKit cache, prints image SHA
# Usage: ./build.sh [tag]  (default: salary-management:local)
#        ./build.sh ghcr.io/OWNER/salary_management:latest --push
#        CELERY_ALWAYS_EAGER=0 ./build.sh  # respects env

IMAGE="${1:-salary-management:local}"
PUSH="${PUSH:-0}"
PLATFORMS="${PLATFORMS:-linux/amd64}"

# Enable BuildKit
export DOCKER_BUILDKIT=1

echo "[build] Building $IMAGE (platforms: $PLATFORMS)..."
echo "[build] Using Dockerfile multi-stage + uv cache (cache-from/to gha if in CI)"

BUILD_ARGS="--build-arg PYTHON_VERSION=3.12 --build-arg UV_VERSION=0.9"

# Local cache dirs (fallback when not in GHA)
if [ "${GITHUB_ACTIONS:-}" = "true" ]; then
  CACHE_FROM="--cache-from type=gha"
  CACHE_TO="--cache-to type=gha,mode=max"
else
  CACHE_FROM=""
  CACHE_TO=""
fi

# Parse extra args (e.g., --push)
EXTRA=""
if [[ "$*" == *"--push"* ]]; then
  EXTRA="--push"
  echo "[build] Will push"
fi

set -x
docker buildx build \
  ${BUILD_ARGS} \
  ${CACHE_FROM} \
  ${CACHE_TO} \
  --file Dockerfile \
  --tag "$IMAGE" \
  --platform "$PLATFORMS" \
  --load \
  ${EXTRA} \
  .

set +x

# Print SHA and size
SHA=$(docker inspect --format='{{index .RepoDigests 0}}' "$IMAGE" 2>/dev/null || echo "no digest (load mode)")
IMAGE_ID=$(docker images --no-trunc --quiet "$IMAGE" | head -n1)
SIZE=$(docker images --format '{{.Size}}' "$IMAGE" | head -n1)

echo "────────────────────────────────────────"
echo "[build] Image: $IMAGE"
echo "[build] Image ID (sha): $IMAGE_ID"
echo "[build] Digest: $SHA"
echo "[build] Size: $SIZE"
echo "[build] SHA: $IMAGE_ID"
echo "────────────────────────────────────────"
echo "Run (eager, no Redis needed):"
echo "  docker run -p 8000:8000 -e DJANGO_SECRET_KEY=dev-secret $IMAGE"
echo "Run with Redis + MinIO:"
echo "  docker run -p 8000:8000 -e CELERY_ALWAYS_EAGER=0 -e CELERY_BROKER_URL=redis://host.docker.internal:6379/0 -e USE_MINIO=1 -e MINIO_ENDPOINT=http://host.docker.internal:9000 $IMAGE"
echo "Celery only:"
echo "  docker run $IMAGE celery"
echo "Shell:"
echo "  docker run -it $IMAGE bash"
echo "────────────────────────────────────────"
echo "Entrypoint handles: migrate, auto-seed (if empty), then server + celery (queue=payroll) when CELERY_ALWAYS_EAGER=0"
# Export SHA for CI
if [ -n "${GITHUB_OUTPUT:-}" ]; then
  echo "image=$IMAGE" >> "$GITHUB_OUTPUT"
  echo "sha=$IMAGE_ID" >> "$GITHUB_OUTPUT"
  echo "digest=$SHA" >> "$GITHUB_OUTPUT"
fi
