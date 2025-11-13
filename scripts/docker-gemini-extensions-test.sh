#!/usr/bin/env bash
set -euo pipefail

# Full Docker test of Gemini extension installation.
#
# Usage:
#   scripts/docker-gemini-extensions-test.sh [<github_url>]
#
# Environment variables:
#   EXT_URL           Git URL to install (default: current repo origin)
#   GEMINI_INSTALL    Command to install the Gemini CLI inside container.
#                     If unset, the script will try several npm package names.
#   IMAGE_TAG         Docker tag to use (default: mcp-shell-aliases:gemini-test)
#
# Example:
#   EXT_URL=https://github.com/you/mcp-shell-aliases \
#   GEMINI_INSTALL="npm i -g @google/gemini-cli" \
#   scripts/docker-gemini-extensions-test.sh

SCRIPT_DIR=$(cd "$(dirname "$0")" && pwd)
REPO_ROOT=$(cd "${SCRIPT_DIR}/.." && pwd)

EXT_URL=${1:-${EXT_URL:-}}
if [[ -z "${EXT_URL}" ]]; then
  if git -C "${REPO_ROOT}" remote get-url origin >/dev/null 2>&1; then
    EXT_URL=$(git -C "${REPO_ROOT}" remote get-url origin)
  else
    echo "[!] EXT_URL not provided and no git remote origin found."
    echo "    Provide the GitHub URL: scripts/docker-gemini-extensions-test.sh https://github.com/<user>/<repo>"
    exit 2
  fi
fi

IMAGE_TAG=${IMAGE_TAG:-mcp-shell-aliases:gemini-test}

echo "[+] Building test image '${IMAGE_TAG}'"
docker build -f "${REPO_ROOT}/docker/Dockerfile.gemini-test" -t "${IMAGE_TAG}" "${REPO_ROOT}"

# Build the install command: either from env or best-effort fallbacks.
if [[ -z "${GEMINI_INSTALL:-}" ]]; then
  # Try a few plausible package names; ignore failures until the last one.
  GEMINI_INSTALL='(npm i -g @google/gemini-cli || npm i -g gemini-cli || npm i -g @google/generative-ai-cli)'
fi

echo "[+] Running container and installing extension from: ${EXT_URL}"
set -x
docker run --rm -e EXT_URL="${EXT_URL}" "${IMAGE_TAG}" \
  bash -lc "set -euo pipefail; \
    node --version; npm --version; python3 --version; \
    ${GEMINI_INSTALL}; \
    command -v gemini >/dev/null 2>&1 || { echo '[!] gemini CLI not found after install'; exit 3; }; \
    gemini --version || true; \
    gemini extensions install \"${EXT_URL}\" --consent; \
    echo; echo '--- gemini extensions list ---'; \
    gemini extensions list | tee /tmp/extensions_list.txt; \
    echo '--------------------------------'; \
    if grep -q "shell-aliases" /tmp/extensions_list.txt; then \
      echo '[OK] Extension shell-aliases appears in gemini extensions list'; \
    else \
      echo '[FAIL] Extension shell-aliases not found in list output' >&2; exit 4; \
    fi"
set +x

echo "[+] Docker Gemini extensions install test succeeded."
