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

from app.tenants import cliente_x


def _make_text_event(from_number: str, text: str) -> dict:
    return {"from": from_number, "type": "text", "text": text}


# ------------------------------------------------------------
# cliente_x.respond
# ------------------------------------------------------------
def test_cliente_x_greeting_uses_env(monkeypatch: pytest.MonkeyPatch):
    # Garante que a automação pode ler variáveis específicas do cliente
    monkeypatch.setenv("CLIENTE_X_GREETING", "Oi! Eu sou o bot da Cliente X (teste).")
    events = [_make_text_event("5561999999999", "olá")]
    actions = cliente_x.respond(events, settings={})
    assert len(actions) == 1
    assert actions[0]["text"].startswith("Oi! Eu sou o bot da Cliente X")


def test_cliente_x_working_hours(monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setenv("CLIENTE_X_WORKING_HOURS", "Atendemos 24/7 (teste).")
    events = [_make_text_event("5561999999999", "qual o horário?")]
    actions = cliente_x.respond(events, settings={})
    assert len(actions) == 1
    assert "24/7" in actions[0]["text"]


def test_cliente_x_menu():
    events = [_make_text_event("5561999999999", "menu")]
    actions = cliente_x.respond(events, settings={})
    assert len(actions) == 1
    assert "Menu Cliente X" in actions[0]["text"]


def test_cliente_x_template():
    events = [_make_text_event("5561999999999", "template hello")]
    actions = cliente_x.respond(events, settings={})
    assert len(actions) == 1
    a = actions[0]
    assert "template" in a and a["template"]["name"] == "hello_world"


def test_cliente_x_fallback():
    events = [_make_text_event("5561999999999", "qualquer coisa")]
    actions = cliente_x.respond(events, settings={})
    assert len(actions) == 1
    assert "Recebi sua mensagem" in actions[0]["text"]
