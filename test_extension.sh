#!/bin/bash

# Exit immediately if a command exits with a non-zero status.
set -e

IMAGE_NAME="mcp-shell-aliases-gemini-extension"
CONTAINER_NAME="mcp-shell-aliases-test-container"
# Placeholder for your private GitHub repository URL
# IMPORTANT: Replace this with the actual URL of your private repository.
# Example: git@github.com:your-org/mcp-shell-aliases.git
GITHUB_REPO_URL="git@github.com:your-org/mcp-shell-aliases.git"

echo "--- Building Docker image: $IMAGE_NAME ---"
docker build -t "$IMAGE_NAME" .

echo "--- Running Docker container with SSH agent forwarding ---"
# This command assumes you have an SSH agent running and 'github.key' added to it.
# For local testing, ensure your SSH agent is running and 'ssh-add github.key' has been executed.
# In a CI/CD environment, this typically involves securely injecting the SSH key.
# The volume mount for the SSH agent socket is crucial for accessing private repos.
docker run -d \
  --name "$CONTAINER_NAME" \
  -v "$(ssh-agent -s | grep SSH_AUTH_SOCK | cut -d';' -f1 | cut -d'=' -f2)":/ssh-agent \
  -e SSH_AUTH_SOCK=/ssh-agent \
  "$IMAGE_NAME" tail -f /dev/null

echo "--- Waiting for container to start... ---"
sleep 5

echo "--- Installing Gemini extension from private GitHub repository ---"
# Execute the gemini extensions install command inside the running container
docker exec "$CONTAINER_NAME" gemini extensions install "$GITHUB_REPO_URL"

echo "--- Verifying Gemini extension installation ---"
# This step is tricky as direct interaction with Gemini CLI's internal state is not straightforward.
# A proxy for verification is to check if the server is running and responsive.
# For a real test, you'd ideally interact with the Gemini CLI itself to list extensions or run a tool.
# For now, we'll assume successful installation if the previous command didn't fail.
echo "Installation command executed. Manual verification within Gemini CLI might be needed."
echo "You can try: docker exec -it $CONTAINER_NAME bash"
echo "Then inside the container: gemini mcp list"
echo "And: /mcp refresh"
echo "And: /tool alias.catalog"

echo "--- Running a test alias (example: 'ls') ---"
# This requires the MCP server to be running and configured within Gemini CLI.
# This part is highly dependent on how Gemini CLI integrates with the MCP server.
# For a full end-to-end test, you would need to simulate Gemini CLI interaction.
# For now, we'll just show how one might attempt to run a tool.
echo "To test an alias, you would typically use the Gemini CLI to call 'alias.exec'."
echo "Example (inside Gemini CLI): /tool alias.exec name=ls args='-la'"

echo "--- Cleaning up container ---"
docker stop "$CONTAINER_NAME"
docker rm "$CONTAINER_NAME"

echo "--- Test script finished. ---"
echo "IMPORTANT: Remember to replace GITHUB_REPO_URL with your actual private repository URL."
echo "And ensure your SSH agent is running and 'github.key' is added to it for the SSH forwarding to work."
