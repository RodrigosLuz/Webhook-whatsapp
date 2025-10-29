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

from app.tenants import default


def _make_text_event(from_number: str, text: str) -> dict:
    return {"from": from_number, "type": "text", "text": text}


# ------------------------------------------------------------
# default.respond
# ------------------------------------------------------------
def test_default_greeting():
    events = [_make_text_event("5561999999999", "oi")]
    actions = default.respond(events, settings={})
    assert len(actions) == 1
    assert "text" in actions[0]
    assert "bot padrão" in actions[0]["text"]


def test_default_template_trigger():
    events = [_make_text_event("5561999999999", "quero template")]
    actions = default.respond(events, settings={})
    assert len(actions) == 1
    assert "template" in actions[0]
    assert actions[0]["template"]["name"] == "hello_world"


def test_default_fallback():
    events = [_make_text_event("5561999999999", "mensagem qualquer")]
    actions = default.respond(events, settings={})
    assert len(actions) == 1
    assert "Recebi sua mensagem" in actions[0]["text"]
