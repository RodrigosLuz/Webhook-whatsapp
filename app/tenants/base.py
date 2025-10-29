# app/tenants/base.py
"""
Define a interface (contrato) para automações de clientes (tenants).

Cada automação deve implementar uma função:
    respond(events: list[dict], settings: dict) -> list[dict]

Essa função recebe a lista de eventos normalizados (ver normalizer.py)
e retorna ações no formato aceito pelo webhook principal:
  - {"to": "5561999999999", "text": "Olá!"}
  - {"to": "5561999999999", "template": {...}}

Você pode criar módulos em app/tenants/<cliente>.py com regras específicas
e registrá-los em tenants/registry.py.

Este módulo apenas define o contrato e fornece uma classe utilitária
para reuso e validação simples.
"""

from __future__ import annotations
from typing import Protocol, List, Dict, Any


class TenantAutomation(Protocol):
    """
    Interface que toda automação de cliente deve seguir.
    """

    def respond(self, events: List[Dict[str, Any]], settings: Dict[str, Any]) -> List[Dict[str, Any]]:
        """
        Recebe eventos normalizados e devolve uma lista de ações.
        """


class BaseTenantAutomation:
    """
    Implementação base opcional.
    - Pode ser herdada por automações mais complexas.
    - Fornece helpers comuns (log, respostas padrão, etc.)
    """

    def __init__(self, name: str):
        self.name = name

    def respond(self, events: List[Dict[str, Any]], settings: Dict[str, Any]) -> List[Dict[str, Any]]:
        """
        Implementação padrão: apenas ecoa o texto recebido.
        """
        actions: List[Dict[str, Any]] = []
        for e in events:
            if e.get("type") == "text":
                txt = str(e.get("text", "")).strip()
                actions.append({"to": e["from"], "text": f"[{self.name}] Você disse: {txt}"})
        return actions
