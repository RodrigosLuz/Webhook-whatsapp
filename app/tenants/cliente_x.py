# app/tenants/cliente_x.py
"""
Automação de exemplo para um cliente específico (cliente_x).

Regras:
- Saúda o usuário com mensagem customizada (pode vir do .env via prefixo CLIENTE_X_*)
- Atende perguntas de horário
- Oferece menu simples
- Permite disparar um template de teste com a frase: "template hello"
- Fallback confirma recebimento

Como configurar variáveis específicas deste cliente no .env:
  CLIENTE_X_GREETING="Oi, eu sou o assistente da Cliente X!"
  CLIENTE_X_WORKING_HOURS="Atendemos 24/7"
"""

from __future__ import annotations

from typing import Any, Dict, List
import os
import re

from app.flows.router import (
    make_text_action,
    make_template_action,
)

# Prefixo para variáveis de ambiente específicas deste cliente
ENV_PREFIX = "CLIENTE_X_"


def _get_var(name: str, default: str | None = None) -> str | None:
    """
    Lê variável de ambiente com prefixo do cliente (ex.: CLIENTE_X_GREETING).
    """
    return os.getenv(f"{ENV_PREFIX}{name}", default)


def _greeting() -> str:
    return _get_var("GREETING", "Olá! Sou o assistente da Cliente X. Como posso ajudar?") or ""


def _working_hours() -> str:
    return _get_var("WORKING_HOURS", "Atendemos de seg a sex, 9h às 18h.") or ""


def respond(events: List[Dict[str, Any]], settings: Dict[str, Any]) -> List[Dict[str, Any]]:
    """
    Função principal da automação do cliente.
    Recebe eventos normalizados e devolve uma lista de ações (text/template).
    """
    actions: List[Dict[str, Any]] = []

    for e in events:
        if e.get("type") != "text":
            # Esta automação trata apenas mensagens de texto por enquanto.
            continue

        to = str(e.get("from", ""))
        txt = str((e.get("text") or "")).strip()
        if not to:
            continue

        txt_norm = txt.lower()

        # 1) Cumprimentos
        if txt_norm in {"oi", "olá", "ola", "bom dia", "boa tarde", "boa noite"}:
            actions.append(make_text_action(to, _greeting()))
            continue

        # 2) Horários
        if re.search(r"\bhor(a|á)rio\b|\bhorario\b", txt_norm):
            actions.append(make_text_action(to, _working_hours()))
            continue

        # 3) Menu
        if re.fullmatch(r"menu", txt_norm, flags=re.IGNORECASE):
            actions.append(
                make_text_action(
                    to,
                    "Menu Cliente X:\n1) Orçamento\n2) Suporte\n3) Falar com humano",
                )
            )
            continue

        # 4) Disparo de template de teste
        if re.fullmatch(r"template\s+hello", txt_norm):
            actions.append(
                make_template_action(
                    to,
                    {
                        "name": "hello_world",
                        "language": {"code": "en_US"},
                    },
                )
            )
            continue

        # 5) Fallback
        actions.append(make_text_action(to, "Recebi sua mensagem! Em instantes te respondo."))

    return actions
