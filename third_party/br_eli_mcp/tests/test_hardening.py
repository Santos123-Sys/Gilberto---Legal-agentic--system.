"""Hardening controls added by this fork (see VENDOR.md). Offline; no network.

Each test pins one control that the upstream release lacked.
"""

from __future__ import annotations

import asyncio
import urllib.request

import pytest

from br_eli_mcp import runtime, server
from br_eli_mcp.cache import HttpCache
from br_eli_mcp.stj_client import DEFAULT_BASE_URL as STJ_DEFAULT
from br_eli_mcp.stj_client import StjClient


def test_runtime_manifest_is_never_fetched(monkeypatch):
    def refuse(*_args, **_kwargs):
        raise AssertionError("runtime manifest must not be fetched")

    monkeypatch.setattr(urllib.request, "urlopen", refuse)
    assert runtime.get_runtime() == {}
    assert runtime.base_url("eli_stj", "https://x.example") == "https://x.example"


def test_base_url_defaults_when_no_override(monkeypatch):
    monkeypatch.delenv("BR_ELI_STJ_BASE_URL", raising=False)
    assert server._stj_base_url() == STJ_DEFAULT


def test_empty_override_uses_default(monkeypatch):
    monkeypatch.setenv("BR_ELI_STJ_BASE_URL", "   ")
    assert server._stj_base_url() == STJ_DEFAULT


def test_https_override_on_same_host_is_accepted(monkeypatch):
    monkeypatch.setenv("BR_ELI_STJ_BASE_URL", STJ_DEFAULT + "/")
    assert server._stj_base_url() == STJ_DEFAULT


@pytest.mark.parametrize("value", [
    "https://evil.example",
    "https://dadosabertos.web.stj.jus.br.evil.example",
    "http://dadosabertos.web.stj.jus.br",
    "https://user:secret@dadosabertos.web.stj.jus.br",
    "https://dadosabertos.web.stj.jus.br:8443",
    "file:///etc/passwd",
])
def test_unsafe_override_is_refused(monkeypatch, value):
    monkeypatch.setenv("BR_ELI_STJ_BASE_URL", value)
    with pytest.raises(RuntimeError):
        server._stj_base_url()


def test_stj_client_does_not_follow_redirects(tmp_path):
    client = StjClient(cache=HttpCache(tmp_path / "cache"))
    try:
        assert client._http.follow_redirects is False
    finally:
        asyncio.run(client.aclose())
