# Copyright 2026 Adobe. All rights reserved.
# Licensed under the Apache License, Version 2.0.

from __future__ import annotations

from aio_runtime.sandbox_api import _build_create_body


class TestBuildCreateBodyPolicy:
    """Verify that _build_create_body forwards the policy field correctly."""

    def test_policy_with_egress_rules(self) -> None:
        policy = {
            "network": {
                "egress": [
                    {"host": "api.github.com", "port": 443},
                    {"host": "*.adobe.io", "port": 443},
                ]
            }
        }
        body = _build_create_body({"name": "sb", "policy": policy})
        assert body["policy"] == policy

    def test_policy_with_allow_all(self) -> None:
        policy = {"network": {"egress": "allow-all"}}
        body = _build_create_body({"name": "sb", "policy": policy})
        assert body["policy"] == {"network": {"egress": "allow-all"}}

    def test_policy_with_empty_egress(self) -> None:
        policy = {"network": {"egress": []}}
        body = _build_create_body({"name": "sb", "policy": policy})
        assert body["policy"] == {"network": {"egress": []}}

    def test_no_policy_omitted_from_body(self) -> None:
        body = _build_create_body({"name": "sb"})
        assert "policy" not in body

    def test_policy_with_protocol(self) -> None:
        policy = {
            "network": {
                "egress": [
                    {"host": "ntp.ubuntu.com", "port": 123, "protocol": "UDP"},
                ]
            }
        }
        body = _build_create_body({"name": "sb", "policy": policy})
        assert body["policy"]["network"]["egress"][0]["protocol"] == "UDP"

    def test_policy_does_not_affect_other_fields(self) -> None:
        policy = {"network": {"egress": "allow-all"}}
        body = _build_create_body({
            "name": "sb",
            "size": "LARGE",
            "max_lifetime": 7200,
            "policy": policy,
        })
        assert body["name"] == "sb"
        assert body["size"] == "LARGE"
        assert body["maxLifetime"] == 7200
        assert body["policy"] == policy
