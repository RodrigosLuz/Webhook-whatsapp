# app/tenants/default.py
"""
Automação padrão (fallback) — usada quando nenhum cliente específico
está registrado para o phone_number_id recebido.

Ideal para:
- testes locais
- ambiente de desenvolvimento
- comportamentos genéricos (ex.: ecoar mensagens)

Pode ser substituída facilmente por um módulo de automação específico.
"""

from __future__ import annotations

from typing import Any, Dict, List
from app.flows.router import make_text_action, make_template_action


def respond(events: List[Dict[str, Any]], settings: Dict[str, Any]) -> List[Dict[str, Any]]:
    """
    Automação padrão — apenas responde de forma genérica às mensagens.
    """
    actions: List[Dict[str, Any]] = []

    for e in events:
        if e.get("type") != "text":
            # Ignora não-texto (ex.: status, imagem)
            continue

        to = str(e.get("from", ""))
        txt = str((e.get("text") or "")).strip()
        if not to:
            continue

        txt_norm = txt.lower()

        if txt_norm in {"oi", "olá", "ola"}:
            actions.append(make_text_action(to, "Oi! Sou o bot padrão. Como posso ajudar?"))
            continue

        if "template" in txt_norm:
            # Envia template de demonstração
            actions.append(
                make_template_action(
                    to,
                    {"name": "hello_world", "language": {"code": "en_US"}},
                )
            )
            continue

        # Fallback
        actions.append(make_text_action(to, "Recebi sua mensagem! Já te respondo."))

    return actions
