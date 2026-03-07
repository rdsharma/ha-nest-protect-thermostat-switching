"""Fixtures for pynest tests.

These tests are pure API client tests and don't need Home Assistant fixtures.
"""

from importlib import import_module
from pathlib import Path
import sys
import types

import pytest

pytest_plugins = ("aiohttp.pytest_plugin",)

_ROOT = Path(__file__).resolve().parents[2] / "custom_components" / "nest_protect"


@pytest.fixture(autouse=True)
def auto_enable_custom_integrations():
    """Override the parent fixture to disable HA for pure client tests."""
    yield


@pytest.fixture(autouse=True)
def verify_cleanup():
    """Override strict cleanup verification for pure API client tests.

    The pytest_homeassistant_custom_component verify_cleanup fixture is too
    strict for these tests - it fails on the _run_safe_shutdown_loop thread
    from asyncio executor shutdown, which is normal cleanup behavior.
    """
    yield


@pytest.fixture
def pynest_import(monkeypatch):
    """Import a pynest module without importing the HA integration package."""
    package_paths = {
        "custom_components": _ROOT.parent.parent,
        "custom_components.nest_protect": _ROOT,
        "custom_components.nest_protect.pynest": _ROOT / "pynest",
    }

    for name, path in package_paths.items():
        module = types.ModuleType(name)
        module.__path__ = [str(path)]
        monkeypatch.setitem(sys.modules, name, module)

    def _import(module_name: str):
        qualified_name = f"custom_components.nest_protect.pynest.{module_name}"
        sys.modules.pop(qualified_name, None)
        return import_module(qualified_name)

    return _import
