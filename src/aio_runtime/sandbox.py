# Copyright 2026 Adobe. All rights reserved.
# Licensed under the Apache License, Version 2.0.

from __future__ import annotations

import asyncio
import base64
import json
import logging
import secrets
import ssl as ssl_module
from collections.abc import Generator
from dataclasses import dataclass, field
from typing import Any, Callable

import httpx
import websockets

from ._http import build_auth_header, sandbox_http_error
from .errors import (
    SandboxClientError,
    SandboxTimeoutError,
    SandboxUnauthorizedError,
    SandboxWebSocketError,
)

logger = logging.getLogger("aio_runtime")


@dataclass
class ExecResult:
    exec_id: str
    stdout: str
    stderr: str
    exit_code: int


@dataclass
class WriteResult:
    path: str
    size: int
    ok: bool


@dataclass
class FileEntry:
    name: str
    type: str
    size: int | None = None


class ExecTask:
    """Awaitable handle for a running command.

    Mirrors the JS SDK pattern where exec() returns a promise with execId.
    Use ``exec_id`` to call ``write_stdin`` / ``close_stdin`` while the
    command runs, then ``await`` the task to get the :class:`ExecResult`.
    """

    def __init__(self, exec_id: str, _task: asyncio.Task[ExecResult]) -> None:
        self.exec_id = exec_id
        self._task = _task

    def __await__(self) -> Generator[Any, None, ExecResult]:
        return self._task.__await__()


@dataclass
class _PendingExec:
    future: asyncio.Future[ExecResult]
    stdout: str = ""
    stderr: str = ""
    on_output: Callable[[str, str], None] | None = None
    timeout_handle: asyncio.TimerHandle | None = None


@dataclass
class _PendingFileOp:
    future: asyncio.Future[Any]


class Sandbox:
    """Connected compute sandbox session over WebSocket."""

    def __init__(
        self,
        *,
        sandbox_id: str,
        endpoint: str,
        status: str,
        cluster: str | None = None,
        region: str | None = None,
        max_lifetime: int = 3600,
        namespace: str,
        api_host: str,
        api_key: str,
        token: str,
        verify_ssl: bool = True,
    ) -> None:
        self.id = sandbox_id
        self.endpoint = endpoint
        self.status = status
        self.cluster = cluster
        self.region = region
        self.max_lifetime = max_lifetime

        self._namespace = namespace
        self._api_host = api_host
        self._api_key = api_key
        self._token = token
        self._verify_ssl = verify_ssl

        self._ws: websockets.ClientConnection | None = None
        self._pending_execs: dict[str, _PendingExec] = {}
        self._pending_file_ops: dict[str, _PendingFileOp] = {}
        self._listener_task: asyncio.Task[None] | None = None

    # ------------------------------------------------------------------
    # Connection
    # ------------------------------------------------------------------

    async def connect(self) -> None:
        if self._ws is not None:
            return

        ssl_ctx = None
        if self.endpoint.startswith("wss://"):
            if self._verify_ssl:
                ssl_ctx = ssl_module.create_default_context()
            else:
                ssl_ctx = ssl_module.SSLContext(ssl_module.PROTOCOL_TLS_CLIENT)
                ssl_ctx.check_hostname = False
                ssl_ctx.verify_mode = ssl_module.CERT_NONE

        try:
            ws = await websockets.connect(
                self.endpoint,
                additional_headers={},
                ssl=ssl_ctx,
            )
        except Exception as exc:
            raise SandboxWebSocketError(
                f"Could not connect sandbox '{self.id}': {exc}"
            ) from exc

        self._ws = ws
        await self._authenticate()
        self._listener_task = asyncio.get_running_loop().create_task(self._listen())

    async def _authenticate(self) -> None:
        await self._send_frame({"type": "auth", "token": self._token})
        raw = await self._ws.recv()
        frame = _parse_frame(raw)
        if not _is_auth_ack(frame, self.id):
            raise SandboxUnauthorizedError(
                f"Sandbox '{self.id}' rejected the WebSocket authentication token"
            )

    # ------------------------------------------------------------------
    # Exec
    # ------------------------------------------------------------------

    def exec(
        self,
        command: str,
        *,
        timeout: float | None = None,
        on_output: Callable[[str, str], None] | None = None,
        stdin: str | bytes | None = None,
    ) -> ExecTask:
        self._ensure_open()
        exec_id = f"exec-{secrets.token_hex(12)}"
        loop = asyncio.get_running_loop()
        future: asyncio.Future[ExecResult] = loop.create_future()
        pending = _PendingExec(future=future, on_output=on_output)

        if timeout is not None:
            pending.timeout_handle = loop.call_later(
                timeout / 1000,
                self._timeout_exec,
                exec_id,
                command,
                timeout,
            )

        self._pending_execs[exec_id] = pending

        async def _run() -> ExecResult:
            await self._send_frame(
                {"type": "exec.run", "execId": exec_id, "command": command}
            )
            if stdin is not None:
                await self.write_stdin(exec_id, stdin)
                await self.close_stdin(exec_id)
            return await future

        return ExecTask(exec_id=exec_id, _task=loop.create_task(_run()))

    async def kill(self, exec_id: str, signal: str = "SIGTERM") -> None:
        self._ensure_open()
        await self._send_frame({"type": "exec.kill", "execId": exec_id, "signal": signal})

    async def write_stdin(self, exec_id: str, data: str | bytes) -> None:
        """Write data to stdin of a running command. Fire-and-forget."""
        self._ensure_open()
        frame: dict[str, Any] = {"type": "exec.input", "execId": exec_id}
        if isinstance(data, bytes):
            frame["data"] = base64.b64encode(data).decode()
            frame["encoding"] = "base64"
        else:
            frame["data"] = data
        await self._send_frame(frame)

    async def close_stdin(self, exec_id: str) -> None:
        """Close stdin for a running command, delivering EOF. Fire-and-forget."""
        self._ensure_open()
        await self._send_frame({"type": "exec.endInput", "execId": exec_id})

    # ------------------------------------------------------------------
    # File operations
    # ------------------------------------------------------------------

    async def read_file(self, path: str) -> str:
        return await self._file_op("file.read", path=path)

    async def write_file(self, path: str, content: str | bytes) -> WriteResult:
        encoded = base64.b64encode(
            content if isinstance(content, bytes) else content.encode()
        ).decode()
        return await self._file_op(
            "file.write", path=path, content=encoded, encoding="base64"
        )

    async def list_files(self, path: str) -> list[FileEntry]:
        return await self._file_op("file.list", path=path)

    async def _file_op(self, frame_type: str, **extra: Any) -> Any:
        self._ensure_open()
        exec_id = f"file-{secrets.token_hex(12)}"
        loop = asyncio.get_running_loop()
        future: asyncio.Future[Any] = loop.create_future()
        self._pending_file_ops[exec_id] = _PendingFileOp(future=future)
        await self._send_frame({"type": frame_type, "execId": exec_id, **extra})
        return await future

    # ------------------------------------------------------------------
    # Destroy
    # ------------------------------------------------------------------

    async def destroy(self) -> dict[str, Any]:
        url = f"{self._api_host}/api/v1/namespaces/{self._namespace}/sandbox/{self.id}"
        headers = {"Authorization": build_auth_header(self._api_key)}

        async with httpx.AsyncClient(verify=self._verify_ssl) as client:
            try:
                resp = await client.delete(url, headers=headers)
            except httpx.HTTPError as exc:
                raise SandboxClientError(
                    f"Could not destroy sandbox '{self.id}': {exc}"
                ) from exc

        if not resp.is_success:
            msg = resp.text
            detail = f"Could not destroy sandbox '{self.id}': {resp.status_code}{f' {msg}' if msg else ''}"
            raise sandbox_http_error(resp.status_code, detail)

        payload = resp.json()
        self.status = payload.get("status", self.status)
        await self._close()
        return payload

    # ------------------------------------------------------------------
    # WebSocket listener
    # ------------------------------------------------------------------

    async def _listen(self) -> None:
        try:
            async for raw in self._ws:
                frame = _parse_frame(raw)
                if frame is None or _is_auth_ack(frame, self.id):
                    continue
                exec_id = frame.get("execId")
                if exec_id in self._pending_file_ops:
                    self._handle_file_frame(frame)
                elif exec_id in self._pending_execs:
                    self._handle_exec_frame(frame)
        except websockets.ConnectionClosed as exc:
            self._reject_all(
                SandboxWebSocketError(
                    f"Sandbox '{self.id}' WebSocket closed with code {exc.code}"
                )
            )
        finally:
            self._ws = None

    # ------------------------------------------------------------------
    # Frame handlers
    # ------------------------------------------------------------------

    def _handle_exec_frame(self, frame: dict[str, Any]) -> None:
        exec_id = frame["execId"]
        pending = self._pending_execs.get(exec_id)
        if pending is None:
            return

        ftype = frame.get("type")

        if ftype == "exec.output":
            data = frame.get("data", "")
            stream = frame.get("stream", "stdout")
            if stream == "stderr":
                pending.stderr += data
            else:
                pending.stdout += data
            if pending.on_output:
                pending.on_output(data, stream)
            return

        if ftype == "exec.exit":
            self._resolve_exec(exec_id, frame)
            return

        if ftype == "error":
            self._reject_pending(
                self._pending_execs,
                exec_id,
                SandboxClientError(frame.get("message", f"Command '{exec_id}' failed")),
            )

    def _handle_file_frame(self, frame: dict[str, Any]) -> None:
        exec_id = frame["execId"]
        pending = self._pending_file_ops.get(exec_id)
        if pending is None:
            return

        ftype = frame.get("type")

        if ftype == "file.content":
            content = frame.get("content", "")
            if frame.get("encoding") == "base64":
                content = base64.b64decode(content).decode()
            self._resolve_file_op(exec_id, content)

        elif ftype == "file.writeResult":
            if not frame.get("ok"):
                self._reject_pending(
                    self._pending_file_ops,
                    exec_id,
                    SandboxClientError(f"file.write failed for path '{frame.get('path')}'"),
                )
            else:
                self._resolve_file_op(
                    exec_id,
                    WriteResult(path=frame["path"], size=frame.get("size", 0), ok=True),
                )

        elif ftype == "file.entries":
            entries = [
                FileEntry(name=e["name"], type=e["type"], size=e.get("size"))
                for e in frame.get("entries", [])
            ]
            self._resolve_file_op(exec_id, entries)

        elif ftype == "error":
            self._reject_pending(
                self._pending_file_ops,
                exec_id,
                SandboxClientError(
                    frame.get("message", f"File operation '{exec_id}' failed")
                ),
            )

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    def _resolve_exec(self, exec_id: str, frame: dict[str, Any]) -> None:
        pending = self._pending_execs.pop(exec_id, None)
        if pending is None:
            return
        if pending.timeout_handle:
            pending.timeout_handle.cancel()
        if not pending.future.done():
            pending.future.set_result(
                ExecResult(
                    exec_id=exec_id,
                    stdout=pending.stdout,
                    stderr=pending.stderr,
                    exit_code=frame.get("exitCode", -1),
                )
            )

    def _resolve_file_op(self, exec_id: str, result: Any) -> None:
        pending = self._pending_file_ops.pop(exec_id, None)
        if pending and not pending.future.done():
            pending.future.set_result(result)

    def _reject_pending(
        self, store: dict[str, Any], exec_id: str, error: Exception
    ) -> None:
        pending = store.pop(exec_id, None)
        if pending is None:
            return
        if hasattr(pending, "timeout_handle") and pending.timeout_handle:
            pending.timeout_handle.cancel()
        if not pending.future.done():
            pending.future.set_exception(error)

    def _reject_all(self, error: Exception) -> None:
        for eid in list(self._pending_execs):
            self._reject_pending(self._pending_execs, eid, error)
        for eid in list(self._pending_file_ops):
            self._reject_pending(self._pending_file_ops, eid, error)

    def _timeout_exec(self, exec_id: str, command: str, timeout: float) -> None:
        try:
            asyncio.get_running_loop().create_task(self.kill(exec_id))
        except Exception:
            pass
        self._reject_pending(
            self._pending_execs,
            exec_id,
            SandboxTimeoutError(
                f"Command '{command}' exceeded timeout of {timeout}ms"
            ),
        )

    def _ensure_open(self) -> None:
        if self._ws is None:
            raise SandboxWebSocketError(f"Sandbox '{self.id}' is not connected")

    async def _send_frame(self, frame: dict[str, Any]) -> None:
        await self._ws.send(json.dumps(frame))

    async def _close(self) -> None:
        if self._listener_task:
            self._listener_task.cancel()
            self._listener_task = None
        if self._ws:
            await self._ws.close()
            self._ws = None


# ------------------------------------------------------------------
# Module-level helpers
# ------------------------------------------------------------------


def _parse_frame(raw: Any) -> dict[str, Any] | None:
    try:
        return json.loads(raw if isinstance(raw, str) else raw.decode())
    except (json.JSONDecodeError, UnicodeDecodeError):
        return None


def _is_auth_ack(frame: dict[str, Any] | None, sandbox_id: str) -> bool:
    if frame is None:
        return False
    return frame.get("type") == "auth.ok" and (
        not frame.get("sandboxId") or frame["sandboxId"] == sandbox_id
    )
