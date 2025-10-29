# tests/unit/test_tenants.py
"""
Testes unitários para automações de tenants:
- default.respond
- cliente_x.respond
- registry.resolve
"""

from __future__ import annotations

import os
import types
import importlib
import pytest

from app.tenants import registry


# ------------------------------------------------------------
# registry.resolve
# ------------------------------------------------------------
def test_registry_resolve_returns_callable():
    app_config = {
        "TENANT_REGISTRY": {
            "111111111111111": "app.tenants.cliente_x",
            "222222222222222": "app.tenants.default",
        }
    }
    fn1 = registry.resolve("111111111111111", app_config)
    fn2 = registry.resolve("222222222222222", app_config)

    assert callable(fn1)
    assert callable(fn2)

    # Sanidade: chamando a função retorna lista de ações (mesmo sem eventos)
    assert isinstance(fn1([], settings={}), list)
    assert isinstance(fn2([], settings={}), list)


def test_registry_resolve_none_for_unknown():
    app_config = {"TENANT_REGISTRY": {"111111111111111": "app.tenants.cliente_x"}}
    fn = registry.resolve("000000000000000", app_config)
    assert fn is None
