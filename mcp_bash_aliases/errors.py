"""Custom exceptions for the MCP Bash Aliases server."""


class AliasError(RuntimeError):
    """Base class for alias related errors."""


class AliasNotFoundError(AliasError):
    """Raised when an alias is not present in the catalog."""


class UnsafeAliasError(AliasError):
    """Raised when execution is requested for an unsafe alias."""


class CwdNotAllowedError(AliasError):
    """Raised when a requested working directory is outside the policy."""


class ExecutionFailure(AliasError):
    """Raised when execution fails before a result can be produced."""

