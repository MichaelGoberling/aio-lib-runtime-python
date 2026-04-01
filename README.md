# aio-lib-runtime-python

Python SDK for Adobe Runtime.

## Install

```bash
pip install git+https://github.com/MichaelGoberling/aio-lib-runtime-python.git
```

> Note: May need to use pip3 on macOS. Requires Python 3.10+.

## Init

```python
from aio_runtime import init

runtime = await init(
    api_host=os.environ.get("AIO_RUNTIME_APIHOST"),
    namespace=os.environ.get("AIO_RUNTIME_NAMESPACE"),
    api_key=os.environ.get("AIO_RUNTIME_AUTH"),
)
```

## Create Sandbox

```python
sandbox = await runtime.compute.sandbox.create(
  name = "my-sandbox",
  type = "cpu:nodejs",
  workspace = "workspace",
  max_lifetime = 3600,
  envs = { "API_KEY": "your-api-key" },
)
```

## Get Status

```python
status = await runtime.compute.sandbox.get_status(sandbox.id)
print("status:", status)
```

## Exec

```python
result = await sandbox.exec("ls -al", timeout=10_000)
print("stdout:", result.stdout.strip())
print("exit code:", result.exit_code)
```

## File Management

```python
script = "console.log('hello from sandbox script', process.version)\n"
await sandbox.write_file("hello.js", script)

content = await sandbox.read_file("hello.js")
print("readFile content:", content.strip())

entries = await sandbox.list_files(".")
print("listFiles entries:", entries)
```

## Exec a File

```python
result = await sandbox.exec("node hello.js", timeout=10_000)
print("stdout:", result.stdout.strip())
print("stderr:", result.stderr.strip())
print("exit code:", result.exit_code)
```

## Curl a site

```python
allowed = await sandbox.exec(
  f'curl -s --connect-timeout 5 -o /dev/null -w "%{{http_code}}" https://github.com',
  timeout = 15_000,
)
print(f"  github.com   (allowed) -> HTTP {allowed.stdout.strip()}")
```

## Write to Stdin

### Command start
```python
result = await sandbox.exec("python process_csv.py", stdin="col1,col2\nval1,val2\n", timeout=10_000)
print("stdout:", result.stdout.strip())
```

### Running command
```python
task = sandbox.exec("cat -n", timeout=10_000)

await sandbox.write_stdin(task.exec_id, "line 1\n")
await sandbox.write_stdin(task.exec_id, "line 2\n")
await sandbox.close_stdin(task.exec_id)

result = await task
print("stdout:", result.stdout.strip())
```

## Destroy

```python
await sandbox.destroy()
```

---

## Network Policies

Sandboxes are default-deny. All outbound traffic is blocked unless explicitly allowed.

Pass a `policy.network.egress` array at creation time to allowlist outbound endpoints, paths, or HTTP verbs.

```python
sandbox = await compute.sandbox.create(
  name="policy-sandbox",
  workspace="policy-test",
  max_lifetime=300,
  policy={
      "network": {
          "egress": [
              {"host": "httpbin.org", "port": 443},
              {
                  "host": "api.github.com",
                  "port": 443,
                  "rules": [
                      {"methods": ["GET"], "pathPattern": "/repos/**"},
                  ],
              },
          ]
      }
  },
)
```

### Allow All (Not recommended for production)

```python
sandbox = await compute.sandbox.create(
  name="policy-allow-all",
  workspace="policy-test",
  max_lifetime=300,
  policy={"network": {"egress": "allow-all"}},
)
```
