# Copyright 2026 Adobe. All rights reserved.
# Licensed under the Apache License, Version 2.0.


class RuntimeSDKError(Exception):
    """Base error for the App Builder Runtime SDK."""

    def __init__(self, message: str = ""):
        self.message = message
        super().__init__(message)


class SDKInitializationError(RuntimeSDKError):
    """Missing or invalid options passed to init()."""


class SandboxClientError(RuntimeSDKError):
    """General sandbox API / client error."""


class SandboxNotFoundError(RuntimeSDKError):
    """Sandbox resource was not found (HTTP 404)."""


class SandboxUnauthorizedError(RuntimeSDKError):
    """Authentication or authorization failure (HTTP 401/403)."""


class SandboxTimeoutError(RuntimeSDKError):
    """Sandbox operation timed out (HTTP 504 or exec timeout)."""


class SandboxWebSocketError(RuntimeSDKError):
    """WebSocket transport error."""
