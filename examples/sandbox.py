"""
Simple example: create a compute sandbox, check its status, run a command, then destroy it.

Usage:
    python examples/sandbox.py
"""

import asyncio

from app_builder_runtime import init


async def main() -> None:
    runtime = await init(
        api_host="http://localhost",
        namespace="namespace",
        api_key="auth",
    )

    sandbox = await runtime.compute.sandbox.create(
        region="us-east-1",
        name="my-sandbox",
        size="MEDIUM",
        type="cpu:nodejs",
        workspace="workspace",
        max_lifetime=3600,
        envs={"API_KEY": "your-api-key"},
    )
    print("sandbox ready:", sandbox.id)

    status = await runtime.compute.sandbox.get_status(sandbox.id)
    print("status:", status)

    print("executing command...")
    result = await sandbox.exec("ls -al", timeout=10_000)
    print("stdout:", result.stdout.strip())
    print("exit code:", result.exit_code)

    print("writing file via write_file...")
    script = "console.log('hello from sandbox script', process.version)\n"
    write_result = await sandbox.write_file("hello.js", script)
    print("write_file result:", write_result)

    print("reading file back via read_file...")
    content = await sandbox.read_file("hello.js")
    print("read_file content:", content.strip())

    print("listing /workspace via list_files...")
    entries = await sandbox.list_files(".")
    print("list_files entries:", entries)

    print("running the script...")
    result2 = await sandbox.exec("node hello.js", timeout=10_000)
    print("stdout:", result2.stdout.strip())
    print("stderr:", result2.stderr.strip())
    print("exit code:", result2.exit_code)

    await sandbox.destroy()
    print("sandbox destroyed")


if __name__ == "__main__":
    asyncio.run(main())
