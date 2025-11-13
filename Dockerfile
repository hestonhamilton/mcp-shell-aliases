# Use a slim Python image as the base
FROM python:3.10-slim

# Set environment variables for non-interactive installation
ENV DEBIAN_FRONTEND=noninteractive

# Install Node.js and npm (required for Gemini CLI)
# Add NodeSource APT repository
RUN apt-get update && apt-get install -y curl gnupg
RUN curl -fsSL https://deb.nodesource.com/setup_20.x | bash -
RUN apt-get install -y nodejs

# Install Gemini CLI globally
RUN npm install -g @google/gemini-cli

# Set the working directory in the container
WORKDIR /app

# Copy the current project files into the container
COPY . /app

# Install Python dependencies for the mcp-shell-aliases server
# The -e flag installs in editable mode, which is useful for development
# and ensures the package is installed correctly for the entrypoint.
RUN pip install -e .

# Expose the default HTTP port for the MCP server, if using HTTP transport
# This is optional if only using stdio, but good for flexibility.
EXPOSE 3921

# Define the default command to run the MCP server
# This can be overridden when running the container
CMD ["python", "-m", "mcp_shell_aliases", "--transport", "stdio"]
