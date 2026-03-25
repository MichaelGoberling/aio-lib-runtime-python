# Copyright 2026 Adobe. All rights reserved.
# Licensed under the Apache License, Version 2.0.

"""App Builder Runtime SDK — compute & sandbox client for Python."""

from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import Any

from .compute import ComputeAPI
from .errors import SDKInitializationError
from .sandbox import ExecResult, FileEntry, Sandbox, WriteResult
from .sandbox_api import (
    SANDBOX_SIZES,
    EgressRule,
    NetworkPolicy,
    Policy,
    SandboxAPI,
)

__all__ = [
    "init",
    "RuntimeClient",
    "ComputeAPI",
    "SandboxAPI",
    "Sandbox",
    "ExecResult",
    "WriteResult",
    "FileEntry",
    "SANDBOX_SIZES",
    "EgressRule",
    "NetworkPolicy",
    "Policy",
]

logger = logging.getLogger("aio_runtime")


@dataclass
class RuntimeClient:
    """Initialised runtime client exposing compute / sandbox APIs."""

    compute: ComputeAPI
    api_host: str
    namespace: str


async def init(
    *,
    api_host: str | None = None,
    namespace: str | None = None,
    api_key: str | None = None,
    verify_ssl: bool = True,
) -> RuntimeClient:
    missing = [
        name
        for name, val in [("api_host", api_host), ("namespace", namespace), ("api_key", api_key)]
        if not val
    ]
    if missing:
        raise SDKInitializationError(
            f"SDK initialization error(s). Missing arguments: {', '.join(missing)}"
        )

    compute = ComputeAPI(api_host, namespace, api_key, verify_ssl=verify_ssl)  # type: ignore[arg-type]
    logger.debug("SDK initialized successfully")

    return RuntimeClient(compute=compute, api_host=api_host, namespace=namespace)  # type: ignore[arg-type]
