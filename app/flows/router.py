# app/flows/router.py
"""
Regras simples de resposta (roteamento) para eventos normalizados.

Este módulo é **puro** (sem Flask/current_app) para facilitar testes e
permanecer estável mesmo quando o app crescer. Ele recebe uma lista de
eventos normalizados (ver normalizer.py) e devolve uma lista de ações.

Formato das ações:
- Mensagem de texto:
  {"to": "5561999999999", "text": "Olá!"}

- Mensagem de template:
  {
    "to": "5561999999999",
    "template": {
      "name": "hello_world",
      "language": {"code": "pt_BR"},
      "components": [...]
    }
  }
"""

from __future__ import annotations

from typing import Any, Dict, List
import re

Action = Dict[str, Any]
Event = Dict[str, Any]


# ------------------------------------------------------------
# Helpers públicos (reutilizados por blueprints para logs etc.)
# ------------------------------------------------------------
def mask_phone(p: str | None) -> str | None:
    if not p:
        return p
    d = re.sub(r"\D", "", str(p))  # apenas dígitos

    # BR: 55 + DD + (4|5) + 2 + 2  -> 12 ou 13 dígitos
    m = re.fullmatch(r"(\d{2})(\d{2})(\d{4,5})(\d{2})(\d{2})", d)
    if m:
        cc, dd, mid, end1, end2 = m.groups()
        return f"{cc}{dd}{re.sub(r'\d', '*', mid)}{end1}{end2}"

    # Fallback seguro para qualquer outro formato:
    n = len(d)
    if n < 7:
        # mantém só os 2 últimos dígitos
        return ("*" * max(0, n - 2)) + d[-2:]
    # mantém 4 primeiros e 2 últimos, mascara o meio
    return d[:4] + ("*" * (n - 6)) + d[-2:]


# ------------------------------------------------------------
# Builders de ações (facilitam os testes e a leitura)
# ------------------------------------------------------------
def make_text_action(to: str, body: str) -> Action:
    return {"to": to, "text": body}


def make_template_action(to: str, template: Dict[str, Any]) -> Action:
    return {"to": to, "template": template}


# ------------------------------------------------------------
# Decisor padrão (fallback) — simples e extensível
# ------------------------------------------------------------
def decide_responses(events: List[Event]) -> List[Action]:
    """
    Regras mínimas de exemplo:
    - "oi"/"olá"/"ola"  -> cumprimento
    - contém "horario"  -> horário de atendimento
    - "menu"            -> opções
    - "template hello"  -> envia template de exemplo (hello_world)
    - default           -> confirmação de recebimento

    Observação: apenas eventos do tipo "text" geram respostas.
    """
    outputs: List[Action] = []

    for e in events:
        if e.get("type") != "text":
            # Ignora não-texto por padrão. Poderia reagir a 'button', etc.
            continue

        to = str(e.get("from", ""))
        txt = str((e.get("text") or "")).strip()

        if not to:
            # Sem destinatário não geramos ação
            continue

        # Normaliza para matching
        txt_norm = txt.lower()

        # 1) Cumprimentos
        if txt_norm in {"oi", "olá", "ola"}:
            outputs.append(make_text_action(to, "Oi! Como posso ajudar?"))
            continue

        # 2) Horário
        if re.search(r"\bhor(a|á)rio\b|\bhorario\b", txt_norm):
            outputs.append(make_text_action(to, "Atendemos de seg a sex, 9h às 18h."))
            continue

        # 3) Menu simples
        if re.fullmatch(r"menu", txt_norm, flags=re.IGNORECASE):
            outputs.append(
                make_text_action(
                    to,
                    "Menu:\n1) Orçamento\n2) Suporte\n3) Falar com humano",
                )
            )
            continue

        # 4) Exemplo: pedido explícito de template (útil para testes)
        #    Mensagem do usuário: "template hello"
        if re.fullmatch(r"template\s+hello", txt_norm):
            outputs.append(
                make_template_action(
                    to,
                    {
                        "name": "hello_world",
                        "language": {"code": "en_US"},
                        # components opcionais; manter vazio para o template hello_world padrão
                    },
                )
            )
            continue

        # 5) Fallback
        outputs.append(make_text_action(to, "Recebi sua mensagem! Já te respondo."))

    return outputs
