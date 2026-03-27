# Copyright 2026 Adobe. All rights reserved.
# Licensed under the Apache License, Version 2.0.

from __future__ import annotations

import asyncio
import base64
import json
from unittest.mock import AsyncMock, patch

import pytest

from aio_runtime.errors import SandboxWebSocketError
from aio_runtime.sandbox import Sandbox


def _make_sandbox(**overrides) -> Sandbox:
    defaults = dict(
        sandbox_id="sb-test",
        endpoint="wss://test.example.com/ws",
        status="Running",
        namespace="ns",
        api_host="https://api.example.com",
        api_key="test-key",
        token="test-token",
    )
    defaults.update(overrides)
    return Sandbox(**defaults)


def _last_sent_frame(ws_mock: AsyncMock) -> dict:
    """Return the most-recently sent JSON frame."""
    return json.loads(ws_mock.send.call_args[0][0])


def _all_sent_frames(ws_mock: AsyncMock) -> list[dict]:
    """Return all JSON frames sent, in order."""
    return [json.loads(call[0][0]) for call in ws_mock.send.call_args_list]


# ------------------------------------------------------------------
# write_stdin
# ------------------------------------------------------------------


class TestWriteStdin:
    @pytest.mark.asyncio
    async def test_write_stdin_text(self) -> None:
        sandbox = _make_sandbox()
        sandbox._ws = AsyncMock()

        await sandbox.write_stdin("exec-abc", 'print("hello")\n')

        sent = _last_sent_frame(sandbox._ws)
        assert sent == {
            "type": "exec.input",
            "execId": "exec-abc",
            "data": 'print("hello")\n',
        }

    @pytest.mark.asyncio
    async def test_write_stdin_bytes(self) -> None:
        sandbox = _make_sandbox()
        sandbox._ws = AsyncMock()
        raw = b"\x00\x01\x02\xff"

        await sandbox.write_stdin("exec-abc", raw)

        sent = _last_sent_frame(sandbox._ws)
        assert sent == {
            "type": "exec.input",
            "execId": "exec-abc",
            "data": base64.b64encode(raw).decode(),
            "encoding": "base64",
        }

    @pytest.mark.asyncio
    async def test_write_stdin_not_connected(self) -> None:
        sandbox = _make_sandbox()

        with pytest.raises(SandboxWebSocketError):
            await sandbox.write_stdin("exec-abc", "data")


# ------------------------------------------------------------------
# close_stdin
# ------------------------------------------------------------------


class TestCloseStdin:
    @pytest.mark.asyncio
    async def test_close_stdin(self) -> None:
        sandbox = _make_sandbox()
        sandbox._ws = AsyncMock()

        await sandbox.close_stdin("exec-abc")

        sent = _last_sent_frame(sandbox._ws)
        assert sent == {
            "type": "exec.endInput",
            "execId": "exec-abc",
        }

    @pytest.mark.asyncio
    async def test_close_stdin_not_connected(self) -> None:
        sandbox = _make_sandbox()

        with pytest.raises(SandboxWebSocketError):
            await sandbox.close_stdin("exec-abc")


# ------------------------------------------------------------------
# exec() with stdin parameter
# ------------------------------------------------------------------


class TestExecWithStdin:
    @pytest.mark.asyncio
    async def test_exec_with_stdin_str(self) -> None:
        sandbox = _make_sandbox()
        sandbox._ws = AsyncMock()

        with patch("aio_runtime.sandbox.secrets.token_hex", return_value="aabbcc"):
            exec_task = sandbox.exec("cat", stdin="hello\n")
            await asyncio.sleep(0)
            sandbox._resolve_exec("exec-aabbcc", {"exitCode": 0})
            result = await exec_task

        frames = _all_sent_frames(sandbox._ws)
        assert len(frames) == 3
        assert frames[0] == {
            "type": "exec.run",
            "execId": "exec-aabbcc",
            "command": "cat",
        }
        assert frames[1] == {
            "type": "exec.input",
            "execId": "exec-aabbcc",
            "data": "hello\n",
        }
        assert frames[2] == {
            "type": "exec.endInput",
            "execId": "exec-aabbcc",
        }
        assert result.exit_code == 0

    @pytest.mark.asyncio
    async def test_exec_with_stdin_bytes(self) -> None:
        sandbox = _make_sandbox()
        sandbox._ws = AsyncMock()
        raw = b"\xde\xad\xbe\xef"

        with patch("aio_runtime.sandbox.secrets.token_hex", return_value="aabbcc"):
            exec_task = sandbox.exec("cat", stdin=raw)
            await asyncio.sleep(0)
            sandbox._resolve_exec("exec-aabbcc", {"exitCode": 0})
            result = await exec_task

        frames = _all_sent_frames(sandbox._ws)
        assert len(frames) == 3
        assert frames[1] == {
            "type": "exec.input",
            "execId": "exec-aabbcc",
            "data": base64.b64encode(raw).decode(),
            "encoding": "base64",
        }
        assert result.exit_code == 0

    @pytest.mark.asyncio
    async def test_exec_without_stdin(self) -> None:
        sandbox = _make_sandbox()
        sandbox._ws = AsyncMock()

        with patch("aio_runtime.sandbox.secrets.token_hex", return_value="aabbcc"):
            exec_task = sandbox.exec("ls")
            await asyncio.sleep(0)
            sandbox._resolve_exec("exec-aabbcc", {"exitCode": 0})
            result = await exec_task

        frames = _all_sent_frames(sandbox._ws)
        assert len(frames) == 1
        assert frames[0] == {
            "type": "exec.run",
            "execId": "exec-aabbcc",
            "command": "ls",
        }
        assert result.exit_code == 0

    @pytest.mark.asyncio
    async def test_exec_task_exposes_exec_id(self) -> None:
        sandbox = _make_sandbox()
        sandbox._ws = AsyncMock()

        with patch("aio_runtime.sandbox.secrets.token_hex", return_value="aabbcc"):
            exec_task = sandbox.exec("cat")

        assert exec_task.exec_id == "exec-aabbcc"

        await asyncio.sleep(0)
        sandbox._resolve_exec("exec-aabbcc", {"exitCode": 0})
        await exec_task


# ------------------------------------------------------------------
# Manual write_stdin / close_stdin via ExecTask.exec_id
# ------------------------------------------------------------------


class TestManualStdinViaExecTask:
    @pytest.mark.asyncio
    async def test_manual_write_stdin(self) -> None:
        sandbox = _make_sandbox()
        sandbox._ws = AsyncMock()

        with patch("aio_runtime.sandbox.secrets.token_hex", return_value="aabbcc"):
            exec_task = sandbox.exec("cat -n")

        await asyncio.sleep(0)

        await sandbox.write_stdin(exec_task.exec_id, "line one\n")
        await sandbox.write_stdin(exec_task.exec_id, "line two\n")
        await sandbox.close_stdin(exec_task.exec_id)

        sandbox._resolve_exec("exec-aabbcc", {"exitCode": 0})
        result = await exec_task

        frames = _all_sent_frames(sandbox._ws)
        assert len(frames) == 4
        assert frames[0] == {
            "type": "exec.run",
            "execId": "exec-aabbcc",
            "command": "cat -n",
        }
        assert frames[1] == {
            "type": "exec.input",
            "execId": "exec-aabbcc",
            "data": "line one\n",
        }
        assert frames[2] == {
            "type": "exec.input",
            "execId": "exec-aabbcc",
            "data": "line two\n",
        }
        assert frames[3] == {
            "type": "exec.endInput",
            "execId": "exec-aabbcc",
        }
        assert result.exit_code == 0
