# Copyright 2026 Adobe. All rights reserved.
# Licensed under the Apache License, Version 2.0.

from __future__ import annotations

from typing import Any

from ._http import api_request, build_ws_endpoint, normalize_api_host
from .errors import SandboxClientError
from .sandbox import Sandbox

SANDBOX_SIZES: dict[str, dict[str, Any]] = {
    "SMALL": {"cpu": "500m", "memory": "512Mi", "gpu": 0},
    "MEDIUM": {"cpu": "2000m", "memory": "4Gi", "gpu": 0},
    "LARGE": {"cpu": "4000m", "memory": "16Gi", "gpu": 0},
    "XLARGE": {"cpu": "8000m", "memory": "32Gi", "gpu": 1},
}


class SandboxAPI:
    """HTTP API for creating and managing compute sandboxes."""

    sizes = SANDBOX_SIZES

    def __init__(
        self,
        api_host: str,
        namespace: str,
        api_key: str,
        *,
        verify_ssl: bool = True,
    ) -> None:
        self._api_host = normalize_api_host(api_host)
        self._namespace = namespace
        self._api_key = api_key
        self._verify_ssl = verify_ssl

    async def create(self, **options: Any) -> Sandbox:
        timeout = options.pop("timeout", 120.0)
        payload = await api_request(
            "POST",
            self._sandbox_url(),
            api_key=self._api_key,
            body=_build_create_body(options),
            verify_ssl=self._verify_ssl,
            timeout=timeout,
            operation="create sandbox",
        )
        return await self._build_sandbox(payload)

    async def get_status(self, sandbox_id: str) -> dict[str, Any]:
        return await api_request(
            "GET",
            f"{self._sandbox_url()}/{sandbox_id}",
            api_key=self._api_key,
            verify_ssl=self._verify_ssl,
            operation="get sandbox status",
        )

    async def _build_sandbox(self, payload: dict[str, Any]) -> Sandbox:
        sandbox_id = payload["sandboxId"]
        endpoint = payload.get("wsEndpoint") or build_ws_endpoint(
            self._api_host, self._namespace, sandbox_id
        )
        sandbox = Sandbox(
            sandbox_id=sandbox_id,
            endpoint=endpoint,
            status=payload.get("status", ""),
            cluster=payload.get("cluster"),
            region=payload.get("region"),
            max_lifetime=payload.get("maxLifetime", 3600),
            namespace=self._namespace,
            api_host=self._api_host,
            api_key=self._api_key,
            token=payload["token"],
            verify_ssl=self._verify_ssl,
        )
        await sandbox.connect()
        return sandbox

    def _sandbox_url(self) -> str:
        if not self._namespace:
            raise SandboxClientError("Sandbox operations require a namespace")
        return f"{self._api_host}/api/v1/namespaces/{self._namespace}/sandbox"


# ------------------------------------------------------------------
# Helpers
# ------------------------------------------------------------------


def _normalize_size(size: str | dict[str, Any] | None) -> str:
    if size is None:
        return "MEDIUM"
    if isinstance(size, str) and size in SANDBOX_SIZES:
        return size
    if isinstance(size, dict):
        for name, spec in SANDBOX_SIZES.items():
            if spec["cpu"] == size.get("cpu") and spec["memory"] == size.get("memory") and spec["gpu"] == size.get("gpu"):
                return name
    raise SandboxClientError("Invalid sandbox size provided")


def _build_create_body(options: dict[str, Any]) -> dict[str, Any]:
    body: dict[str, Any] = {
        "name": options.get("name"),
        "size": _normalize_size(options.get("size")),
        "type": options.get("type", "cpu:default"),
        "maxLifetime": options.get("max_lifetime", 3600),
    }
    for key in ("cluster", "region", "workspace", "envs"):
        if key in options:
            body[key] = options[key]
    return body
