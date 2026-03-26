# aio-lib-runtime-python

Python SDK for Adobe Runtime.

## Install

```bash
pip install git+https://github.com/MichaelGoberling/aio-lib-runtime-python.git
```

> Note: Use `pip3` on macOS if needed. Requires Python 3.10+.

## Quick Start

Every example below assumes you have a `runtime` instance and a `sandbox` ready to go:

```python
import asyncio
from aio_runtime import init

async def main():
    runtime = await init(
        api_host="https://<your-host>",
        namespace="<your-namespace>",
        api_key="<your-api-key>",
    )

    sandbox = await runtime.compute.sandbox.create(
        name="my-sandbox",
        size="MEDIUM",           # SMALL | MEDIUM | LARGE | XLARGE
        max_lifetime=3600,       # seconds
    )

    result = await sandbox.exec("echo hello")
    print(result.stdout)

    await sandbox.destroy()

asyncio.run(main())
```

---

## Examples

### Getting Status

Query a sandbox's current status by its ID:

```python
status = await runtime.compute.sandbox.get_status(sandbox.id)
print(status)
# {'sandboxId': 'abc-123', 'status': 'running', 'cluster': 'us-east', ...}
```

### Managing Files

**Write a file** into the sandbox:

```python
await sandbox.write_file("hello.js", "console.log('hello world');\n")
```

**Read a file** back:

```python
content = await sandbox.read_file("hello.js")
print(content)  # console.log('hello world');
```

**List files** in a directory:

```python
entries = await sandbox.list_files(".")
for entry in entries:
    print(f"{entry.name}  ({entry.type}, {entry.size} bytes)")
```

### Exec-ing a File

Write a script, then execute it:

```python
script = """\
import json, sys
print(json.dumps({"python": sys.version, "status": "ok"}))
"""

await sandbox.write_file("check.py", script)

result = await sandbox.exec("python3 check.py", timeout=10_000)
print(result.stdout)       # {"python": "3.12.x", "status": "ok"}
print(result.exit_code)    # 0
```

You can also stream output as it arrives:

```python
def on_output(data: str, stream: str) -> None:
    print(f"[{stream}] {data}", end="")

result = await sandbox.exec("npm install", timeout=30_000, on_output=on_output)
```

### Curling a Site with a Network Policy

Create a sandbox with an egress allowlist so it can only reach specific hosts:

```python
sandbox = await runtime.compute.sandbox.create(
    name="locked-down",
    size="MEDIUM",
    max_lifetime=300,
    policy={
        "network": {
            "egress": [
                {"host": "httpbin.org", "port": 443},
            ]
        }
    },
)

# Allowed — httpbin.org is in the allowlist
allowed = await sandbox.exec(
    'curl -s -o /dev/null -w "%{http_code}" https://httpbin.org/get',
    timeout=15_000,
)
print(f"httpbin.org  -> HTTP {allowed.stdout.strip()}")  # 200

# Blocked — example.com is NOT in the allowlist
blocked = await sandbox.exec(
    'curl -s --connect-timeout 5 -o /dev/null -w "%{http_code}" https://example.com || echo "BLOCKED"',
    timeout=15_000,
)
print(f"example.com  -> {blocked.stdout.strip()}")  # BLOCKED
```

To allow all outbound traffic instead, pass `"allow-all"`:

```python
sandbox = await runtime.compute.sandbox.create(
    name="open-egress",
    size="MEDIUM",
    policy={"network": {"egress": "allow-all"}},
)
```

Omitting the `policy` key entirely applies the default-deny baseline (only internal DNS and NATS are reachable).

---

See [`examples/sandbox.py`](examples/sandbox.py) for a full interactive walkthrough.
