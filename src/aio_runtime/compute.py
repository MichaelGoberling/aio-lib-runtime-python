# Copyright 2026 Adobe. All rights reserved.
# Licensed under the Apache License, Version 2.0.

from __future__ import annotations

from .sandbox_api import SandboxAPI


class ComputeAPI:
    """Compute management API — exposes sandbox lifecycle operations."""

    def __init__(
        self,
        api_host: str,
        namespace: str,
        api_key: str,
        *,
        verify_ssl: bool = True,
    ) -> None:
        self.sandbox = SandboxAPI(
            api_host, namespace, api_key, verify_ssl=verify_ssl
        )
