# aio-lib-runtime-python

Python SDK for Adobe Runtime.

## Install

```bash
pip install git+https://github.com/MichaelGoberling/aio-lib-runtime-python.git
```

> Note: Use `pip3` on macOS if needed. Requires Python 3.10+.

## Usage

```python
import asyncio
from aio_runtime import init

async def main():
    runtime = await init(
        api_host="https://<your-host>",
        namespace="<your-namespace>",
        api_key="<your-api-key>",
    )

    sandbox = await runtime.compute.sandbox.create(size="MEDIUM")

    result = await sandbox.exec("echo hello")
    print(result.stdout)

    await sandbox.destroy()

asyncio.run(main())
```

See [`sandbox.py`](examples/sandbox.py) for a full walkthrough.
