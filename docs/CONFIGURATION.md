# Configuration Reference

The MCP Shell Aliases server is configured via a YAML file (default `config.yaml`). Values can also be overridden with CLI flags or environment variables prefixed with `MCP_SHELL_ALIASES_`.

## Top-Level Fields

- `alias_files` (`list[str]`, default: `[]`)
  Explicit alias files to parse. Entries expand `~` to the user's home directory and resolve relative to the config file's directory. Files are read in order; later files override earlier definitions.
- `allow_patterns` (`list[str]`)
  Regex patterns that mark alias expansions as safe for execution. Patterns are
  decoded with Python's escape sequences, so `"^ls\\b"` and `"^ls\b"` are treated
  the same. Any alias expansion that fails to match stays in dry-run mode. The
  previous denylist has been removed for stronger, allowlist-only safety.
- `default_cwd` (`str`, default: `~`)
  Default working directory if callers do not provide one.
- `allow_cwd_roots` (`list[str]`, default: `["~"]`)
  Whitelisted directory roots for execution. Requests outside these roots are rejected.
- `audit_log_path` (`str`)
  File path for JSON lines audit logs (folders are created automatically).
- `enable_hot_reload` (`bool`, default: `true`)
  When enabled, the catalog reloads alias files on every request.
- `transport` (`str`, default: `stdio`)
  Allowed values: `stdio`, `http`, `streamable-http`, or `sse`.
- `http_host` (`str`, default: `127.0.0.1`)
  Host binding for HTTP/SSE transports.
- `http_port` (`int`, default: `3921`)
  Port binding for HTTP/SSE transports.
- `http_path` (`str`, default: `/mcp`)
  URL path exposed when serving HTTP/SSE. A leading slash is added automatically.

> **Heads-up:** legacy `deny_patterns` entries are rejected at load time. Remove the field and expand the
> allowlist instead.

### Example `config.yaml`

#### Stdio transport (default)

```yaml
alias_files:
  - ~/.bash_aliases
allow_patterns:
  - '^ls\b'
  - '^git\b(?!\s+(push|reset|rebase|clean))'
default_cwd: '~'
allow_cwd_roots:
  - '~'
audit_log_path: '~/.local/state/mcp-shell-aliases/audit.log'
execution:
  max_stdout_bytes: 10000
  max_stderr_bytes: 10000
  default_timeout_seconds: 20
enable_hot_reload: true
transport: stdio
```

#### HTTP transport for local agents

```yaml
alias_files:
  - ~/.bash_aliases
allow_patterns:
  - '^ls\b'
  - '^rg\b'
default_cwd: '~'
allow_cwd_roots:
  - '~'
execution:
  max_stdout_bytes: 15000
  max_stderr_bytes: 15000
  default_timeout_seconds: 20
enable_hot_reload: false
transport: http
http_host: 127.0.0.1
http_port: 3921
http_path: /mcp
```

Set `transport` to `streamable-http` or `sse` if your host requires those
variants. Hosts should point at `http://<http_host>:<http_port><http_path>`.

## Execution Limits

```yaml
execution:
  max_stdout_bytes: 10000
  max_stderr_bytes: 10000
  default_timeout_seconds: 20
```

- `max_stdout_bytes` / `max_stderr_bytes`
  Upper bounds for captured output; excess is truncated and flagged.
- `default_timeout_seconds`
  Timeout for alias execution unless the caller provides `timeout_seconds`.

## Environment Variables

Environment variable overrides use uppercase keys. Examples:

- `MCP_SHELL_ALIASES_ALIAS_FILES="~/.bash_aliases:~/.bashrc"`
- `MCP_SHELL_ALIASES_ENABLE_HOT_RELOAD=false`
- `MCP_SHELL_ALIASES_DEFAULT_TIMEOUT_SECONDS=10`
- `MCP_SHELL_ALIASES_ALLOW_CWD_ROOTS="~:~/projects"`
- `MCP_SHELL_ALIASES_TRANSPORT=http`
- `MCP_SHELL_ALIASES_HTTP_HOST=0.0.0.0`
- `MCP_SHELL_ALIASES_HTTP_PORT=3921`
- `MCP_SHELL_ALIASES_HTTP_PATH=/mcp`

List values are colon-delimited. If `ALLOW_CWD_ROOTS` is empty, the server falls
back to `default_cwd`.

## CLI Flags

Selected overrides are available on the CLI:

- `--alias-file ~/.bash_aliases`
- `--allow-pattern '^git\b'`
- `--default-cwd ~/workspace`
- `--hot-reload/--no-hot-reload`
- `--max-stdout-bytes 2048`
- `--max-stderr-bytes 2048`
- `--timeout 15`
- `--allow-cwd-root ~/projects`
- `--transport http`
- `--http-host 0.0.0.0`
- `--http-port 3921`
- `--http-path /mcp`


## Connecting to AI Assistants

You can connect the MCP Shell Aliases server to various AI assistants that support custom tools.

### Gemini CLI

The Gemini CLI can connect to MCP servers.

#### Gemini Extension Configuration (`gemini-extension.json`)

When installing the `mcp-shell-aliases` server as a Gemini extension using `gemini extensions install <github_url>`, the Gemini CLI reads the `gemini-extension.json` file from the root of the repository. This file defines how the MCP server should be launched.

A typical `gemini-extension.json` for this project would look like this:

```json
{
  "name": "shell-aliases",
  "version": "0.1.0",
  "description": "Expose shell aliases as safe MCP tools via FastMCP.",
  "author": "Gemini Shell Aliases Team",
  "license": "MIT",
  "mcp_server": {
    "command": [
      "python",
      "-m",
      "mcp_shell_aliases",
      "--config",
      "${extensionPath}/config.yaml"
    ]
  },
  "configuration": {
    "aliasFiles": [
      "~/.bash_aliases"
    ]
  }
}
```

In this configuration:
- The `mcp_server.command` specifies the executable and arguments to run the MCP server. `${extensionPath}` is a variable that resolves to the installation directory of the extension.
- The `configuration` block allows the extension to provide default settings that can be overridden by the user.

#### Direct Server Connection (`gemini mcp add`)

If you are running the server independently (not as an installed extension) and want to connect the Gemini CLI to it, you can use the `gemini mcp add` command.

##### Stdio Transport

If you are running the server with `transport: stdio` (the default), you can add it with the following command:

```bash
gemini mcp add mcp-shell-aliases python -m mcp_shell_aliases --config /path/to/your/config.yaml
```

This will add the server to your project's `.gemini/settings.json` file. Use the `--scope user` flag to add it to your global `~/.gemini/settings.json` file.

##### HTTP Transport

If you are running the server with `transport: http`, `streamable-http`, or `sse`, you can add it with the following command:

```bash
gemini mcp add mcp-shell-aliases http://127.0.0.1:3921/mcp --transport http
```

**Note:** For HTTP and SSE transports, the `mcp-shell-aliases` server must be running independently before you add it to the Gemini CLI. The CLI will not automatically start HTTP/SSE servers.

After adding the server, run `/mcp refresh` in the Gemini CLI to see the new tools.

For manual configuration, you can create or edit `.gemini/settings.json` in your project directory or `~/.gemini/settings.json` globally and add an `mcpServers` block.

<details>
<summary>Manual Configuration Examples</summary>

##### Stdio Transport

```json
{
  "mcpServers": {
    "mcp-shell-aliases": {
      "command": ["python", "-m", "mcp_shell_aliases"],
      "args": ["--config", "/path/to/your/config.yaml"]
    }
  }
}
```

Replace the `command` and `args` with the correct path to your python executable and `config.yaml`.

##### HTTP Transport

```json
{
  "mcpServers": {
    "mcp-shell-aliases": {
      "httpUrl": "http://127.0.0.1:3921/mcp"
    }
  }
}
```

</details>

### OpenAI API

To use this server with the OpenAI API, you can define a "tool" for the model to call. This requires custom code on your part to handle the API interaction.

Here is an example of a tool definition you could use in your application:

```json
{
  "type": "function",
  "function": {
    "name": "run_shell_alias",
    "description": "Runs a shell alias or command and returns the output. Use this to interact with the local shell.",
    "parameters": {
      "type": "object",
      "properties": {
        "command": {
          "type": "string",
          "description": "The shell alias or command to run."
        },
        "cwd": {
          "type": "string",
          "description": "The working directory to run the command in. Defaults to the user's home directory."
        }
      },
      "required": ["command"]
    }
  }
}
```

Your application would then receive a request from the model to call this function, and you would make a request to the `mcp-shell-aliases` server (running in HTTP mode) and return the output to the model.

### Anthropic Claude

Claude supports the Model Context Protocol (MCP) directly. If you are using a Claude client that supports MCP (like some versions of Claude Desktop), you can configure it to connect to your `mcp-shell-aliases` server.

Look for a setting in your Claude client to add a custom MCP server. You will need to provide the URL of your server, for example: `http://127.0.0.1:3921/mcp`.

Once configured, Claude will be able to see and use the shell aliases you have exposed.
