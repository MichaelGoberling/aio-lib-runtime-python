# Copyright 2026 Adobe. All rights reserved.
# Licensed under the Apache License, Version 2.0.

"""
Pre-built network policies for common services.

Each attribute is a ``{"egress": [...]}`` dict that can be passed directly
as the ``network`` field when creating a sandbox::

    from aio_runtime import NetworkPolicy

    sandbox = await compute.sandbox.create(
        name="my-agent",
        policy={"network": NetworkPolicy.base},
    )

Modelled after https://github.com/NVIDIA/OpenShell-Community/blob/main/sandboxes/base/policy.yaml
"""

from __future__ import annotations

from .sandbox_api import EgressRule, NetworkPolicyOptions


def _policy(*rules: EgressRule) -> NetworkPolicyOptions:
    return {"egress": list(rules)}


class NetworkPolicy:
    """Pre-built network policies keyed by service name."""

    # -- AI / LLM providers --------------------------------------------------

    anthropic: NetworkPolicyOptions = _policy(
        {"host": "api.anthropic.com", "port": 443},
        {"host": "statsig.anthropic.com", "port": 443},
        {"host": "sentry.io", "port": 443},
    )

    # -- GitHub --------------------------------------------------------------

    github: NetworkPolicyOptions = _policy(
        {"host": "github.com", "port": 443},
        {"host": "api.github.com", "port": 443},
        {"host": "objects.githubusercontent.com", "port": 443},
        {"host": "raw.githubusercontent.com", "port": 443},
        {"host": "release-assets.githubusercontent.com", "port": 443},
    )

    github_copilot: NetworkPolicyOptions = _policy(
        {"host": "github.com", "port": 443},
        {"host": "api.github.com", "port": 443},
        {"host": "api.githubcopilot.com", "port": 443},
        {"host": "api.enterprise.githubcopilot.com", "port": 443},
        {"host": "release-assets.githubusercontent.com", "port": 443},
        {"host": "copilot-proxy.githubusercontent.com", "port": 443},
        {"host": "default.exp-tas.com", "port": 443},
    )

    # -- Package registries --------------------------------------------------

    pypi: NetworkPolicyOptions = _policy(
        {"host": "pypi.org", "port": 443},
        {"host": "files.pythonhosted.org", "port": 443},
        {"host": "downloads.python.org", "port": 443},
    )

    npm: NetworkPolicyOptions = _policy(
        {"host": "registry.npmjs.org", "port": 443},
    )

    # -- AI coding tools -----------------------------------------------------

    opencode: NetworkPolicyOptions = _policy(
        {"host": "registry.npmjs.org", "port": 443},
        {"host": "opencode.ai", "port": 443},
        {"host": "integrate.api.nvidia.com", "port": 443},
    )

    # -- IDEs / editors ------------------------------------------------------

    vscode: NetworkPolicyOptions = _policy(
        {"host": "update.code.visualstudio.com", "port": 443},
        {"host": "az764295.vo.msecnd.net", "port": 443},
        {"host": "vscode.download.prss.microsoft.com", "port": 443},
        {"host": "marketplace.visualstudio.com", "port": 443},
        {"host": "gallerycdn.vsassets.io", "port": 443},
    )

    cursor: NetworkPolicyOptions = _policy(
        {"host": "cursor.blob.core.windows.net", "port": 443},
        {"host": "api2.cursor.sh", "port": 443},
        {"host": "repo.cursor.sh", "port": 443},
        {"host": "download.cursor.sh", "port": 443},
        {"host": "cursor.download.prss.microsoft.com", "port": 443},
    )

    # -- Base policy ---------------------------------------------------------
    # GitHub + PyPI + npm + Anthropic

    base: NetworkPolicyOptions = {
        "egress": [
            *github["egress"],
            *pypi["egress"],
            *npm["egress"],
            *anthropic["egress"],
        ]
    }
