#!/usr/bin/env bash
set -euo pipefail

IMAGE_TAG="mcp-shell-aliases:smoke"

echo "[+] Building smoke-test image: ${IMAGE_TAG}"
docker build -f docker/Dockerfile.smoke -t "${IMAGE_TAG}" .

echo "[+] Running container (HTTP mode on :3921). Press Ctrl+C to stop."
docker run --rm -p 3921:3921 "${IMAGE_TAG}"

