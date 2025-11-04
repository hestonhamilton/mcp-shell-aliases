# Configuration Reference

The MCP Bash Aliases server is configured via a YAML file (default `config.yaml`). Values can also be overridden with CLI flags or environment variables prefixed with `MCP_BASH_ALIASES_`.

## Top-Level Fields

- `alias_files` (`list[str]`, default: `[]`)
  Explicit alias files to parse. Entries expand `~` to the user's home directory and resolve relative to the config file's directory. Files are read in order; later files override earlier definitions.
- `allow_patterns` (`list[str]`)
  Regex patterns that mark alias expansions as safe for execution. Patterns are
  decoded with Python's escape sequences, so `"^ls\\b"` and `"^ls\b"` are treated
  the same.
- `deny_patterns` (`list[str]`)
  Regex patterns that block execution regardless of allow rules.
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

### Example `config.yaml`

#### Stdio transport (default)

```yaml
alias_files:
  - ~/.bash_aliases
allow_patterns:
  - '^ls\b'
  - '^git\b(?!\s+(push|reset|rebase|clean))'
deny_patterns:
  - '^rm\b'
default_cwd: '~'
allow_cwd_roots:
  - '~'
audit_log_path: '~/.local/state/mcp-bash-aliases/audit.log'
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
deny_patterns:
  - '^rm\b'
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

- `MCP_BASH_ALIASES_ALIAS_FILES="~/.bash_aliases:~/.bashrc"`
- `MCP_BASH_ALIASES_ENABLE_HOT_RELOAD=false`
- `MCP_BASH_ALIASES_DEFAULT_TIMEOUT_SECONDS=10`
- `MCP_BASH_ALIASES_ALLOW_CWD_ROOTS="~:~/projects"`
- `MCP_BASH_ALIASES_TRANSPORT=http`
- `MCP_BASH_ALIASES_HTTP_HOST=0.0.0.0`
- `MCP_BASH_ALIASES_HTTP_PORT=3921`
- `MCP_BASH_ALIASES_HTTP_PATH=/mcp`

List values are colon-delimited. If `ALLOW_CWD_ROOTS` is empty, the server falls
back to `default_cwd`.

## CLI Flags

Selected overrides are available on the CLI:

- `--alias-file ~/.bash_aliases`
- `--allow-pattern '^git\b'`
- `--deny-pattern '^rm\b'`
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

You can connect the MCP Bash Aliases server to various AI assistants that support custom tools.

### Gemini CLI

The Gemini CLI can connect to MCP servers. Create or edit `.gemini/settings.json` in your project directory or `~/.gemini/settings.json` globally and add an `mcpServers` block.

#### Stdio Transport

If you are running the server with `transport: stdio` (the default), you can connect to it with a `command`:

```json
{
  "mcpServers": [
    {
      "command": ["python", "-m", "mcp_bash_aliases"],
      "args": ["--config", "/path/to/your/config.yaml"]
    }
  ]
}
```

Replace the `command` and `args` with the correct path to your python executable and `config.yaml`.

#### HTTP Transport

If you are running the server with `transport: http`, `streamable-http`, or `sse`, you can connect to it with a `url`:

```json
{
  "mcpServers": [
    {
      "httpUrl": "http://127.0.0.1:3921/mcp"
    }
  ]
}
```

After editing `settings.json`, run `/mcp refresh` in the Gemini CLI to see the new tools.

### OpenAI API

To use this server with the OpenAI API, you can define a "tool" for the model to call. This requires custom code on your part to handle the API interaction.

Here is an example of a tool definition you could use in your application:

```json
{
  "type": "function",
  "function": {
    "name": "run_bash_alias",
    "description": "Runs a bash alias or command and returns the output. Use this to interact with the local shell.",
    "parameters": {
      "type": "object",
      "properties": {
        "command": {
          "type": "string",
          "description": "The bash alias or command to run."
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

Your application would then receive a request from the model to call this function, and you would make a request to the `mcp-bash-aliases` server (running in HTTP mode) and return the output to the model.

### Anthropic Claude

Claude supports the Model Context Protocol (MCP) directly. If you are using a Claude client that supports MCP (like some versions of Claude Desktop), you can configure it to connect to your `mcp-bash-aliases` server.

Look for a setting in your Claude client to add a custom MCP server. You will need to provide the URL of your server, for example: `http://127.0.0.1:3921/mcp`.

Once configured, Claude will be able to see and use the bash aliases you have exposed.
