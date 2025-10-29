# app/tenants/cliente_x.py
"""
Automação de exemplo para um cliente específico (cliente_x) — agora com estados de conversa (Session Manager).

Regras (mantidas e expandidas):
- Saúda o usuário (ENV CLIENTE_X_GREETING)
- Informa horário (ENV CLIENTE_X_WORKING_HOURS)
- "menu" → envia menu e muda estado para awaiting_menu_selection   [NOVO]
- "1" (se aguardando menu) → pedir nome e mudar para awaiting_name [NOVO]
- "2" (se aguardando menu) → pedir descrição de suporte            [NOVO]
- "3" (se aguardando menu) → escalar p/ humano (state=escalated)   [NOVO]
- Qualquer texto em awaiting_name → salvar nome e voltar ao menu   [NOVO]
- Confirmação de nome vindo da Meta (state=awaiting_name_confirm)  [NOVO]
- "template hello" → envia template de teste (como antes)
- Fallback → confirmação de recebimento

Observações:
- Usa SessionManager em memória. O tenant (PNID) é recuperado pela sessão criada no webhook.
- Se você já adotou chave composta (tenant, phone) no SessionManager, os helpers abaixo lidam com isso.
"""

from __future__ import annotations

from typing import Any, Dict, List, Optional, Tuple
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


# [NOVO] --------- helpers de menu/estado ---------
def _menu_text(nome: Optional[str] = None) -> str:
    """Monta o texto do menu, usando o nome se já estiver no contexto."""
    prefix = f"{nome}, segue o menu:\n" if nome else "Menu Cliente X:\n"
    return (
        prefix
        + "1) Orçamento\n"
        + "2) Suporte\n"
        + "3) Falar com humano"
    )


# [NOVO] --------- utilitários para confirmação de nome ---------
YES_RE  = re.compile(r"^(s|sim|ok|isso|pode|claro)\b", re.IGNORECASE)
NO_RE   = re.compile(r"^(n|nao|não|negativo)\b", re.IGNORECASE)

def _looks_like_name(s: str) -> bool:
    s = s.strip()
    # heurística leve: contém letras e tem pelo menos 2 chars
    return bool(re.search(r"[A-Za-zÀ-ÖØ-öø-ÿ]", s)) and len(s) >= 2


# [NOVO] --------- helpers de sessão (compatíveis com as 2 versões do SessionManager) ---------
def _get_sm(settings: Dict[str, Any]):
    """Pega o SessionManager in-memory da app (configurado em app/__init__.py)."""
    return settings.get("SESSION_MANAGER")

def _find_tenant_for_phone(sm, phone: str) -> Optional[str]:
    """
    Recupera o tenant (PNID) da sessão aberta para este phone.
    Funciona quando o SessionManager usa chave (tenant, phone) no dict interno.
    """
    try:
        snap = sm.snapshot()  # dict[ (tenant, phone) ] -> session
        for key, sess in snap.items():
            # key pode ser tupla (tenant, phone) ou string (phone) dependendo da sua versão
            if isinstance(key, tuple) and len(key) == 2:
                _tenant, _phone = key
                if str(_phone) == str(phone):
                    return str(_tenant)
            else:
                # fallback: versão antiga indexada só por phone
                if str(key) == str(phone):
                    return str(sess.get("tenant") or "unknown")
    except Exception:
        pass
    return None

def _get_session(sm, tenant: Optional[str], phone: str) -> Optional[Dict[str, Any]]:
    """Obtém a sessão atual, tentando a assinatura nova (tenant+phone) e a antiga (phone)."""
    if not sm:
        return None
    try:
        if tenant is not None:
            return sm.get(tenant=tenant, phone=phone)  # nova assinatura
    except TypeError:
        pass
    # fallback assinatura antiga (somente phone)
    try:
        return sm.get(phone)  # type: ignore[arg-type]
    except Exception:
        return None

def _set_state(sm, tenant: Optional[str], phone: str, state: str) -> None:
    """Define o estado atual com compatibilidade de assinatura."""
    if not sm:
        return
    try:
        if tenant is not None:
            sm.set_state(tenant=tenant, phone=phone, state=state)
            return
    except TypeError:
        pass
    # fallback assinatura antiga
    try:
        sm.set_state(phone, state)  # type: ignore[misc]
    except Exception:
        pass

def _set_ctx(sm, tenant: Optional[str], phone: str, updates: Dict[str, Any]) -> None:
    """Atualiza o contexto com compatibilidade de assinatura."""
    if not sm:
        return
    try:
        if tenant is not None:
            sm.set_context(tenant=tenant, phone=phone, updates=updates)
            return
    except TypeError:
        pass
    # fallback assinatura antiga
    try:
        sm.set_context(phone, updates)  # type: ignore[misc]
    except Exception:
        pass
# [FIM NOVO helpers de sessão]


def respond(events: List[Dict[str, Any]], settings: Dict[str, Any]) -> List[Dict[str, Any]]:
    """
    Função principal da automação do cliente.
    Recebe eventos normalizados e devolve uma lista de ações (text/template).
    """
    actions: List[Dict[str, Any]] = []

    # [NOVO] pega o session manager
    sm = _get_sm(settings)

    for e in events:
        if e.get("type") != "text":
            # Esta automação trata apenas mensagens de texto por enquanto.
            continue

        to = str(e.get("from", ""))
        txt = str((e.get("text") or "")).strip()
        if not to:
            continue

        txt_norm = txt.lower()

        # [NOVO] tenta descobrir o tenant (PNID) pela sessão criada no webhook
        tenant = _find_tenant_for_phone(sm, to) if sm else None

        # [NOVO] obtém sessão, estado atual e contexto
        sess = _get_session(sm, tenant, to) if sm else None
        state = (sess or {}).get("state") or "idle"
        ctx = (sess or {}).get("context") or {}
        nome = ctx.get("nome")
        profile_name = ctx.get("profile_name")  # [NOVO]

        # 1) Cumprimentos (mantido)
        if txt_norm in {"oi", "olá", "ola", "bom dia", "boa tarde", "boa noite"}:
            actions.append(make_text_action(to, _greeting()))
            # estado não muda
            continue

        # 2) Horários (mantido)
        if re.search(r"\bhor(a|á)rio\b|\bhorario\b", txt_norm):
            actions.append(make_text_action(to, _working_hours()))
            # estado não muda
            continue

        # [NOVO] 2.5) Confirmação de nome vindo da Meta (antes do menu)
        # só pergunta se ainda não temos 'nome' e não estamos no meio de uma coleta de nome/suporte/menu
        if (
            not nome
            and profile_name
            and state not in {"awaiting_name", "awaiting_name_confirm", "awaiting_menu_selection", "awaiting_support_desc"}
        ):
            actions.append(
                make_text_action(
                    to,
                    f"Posso te chamar de {profile_name}? Se preferir outro nome, me diga 🙂"
                )
            )
            _set_state(sm, tenant, to, "awaiting_name_confirm")
            continue

        # 3) Menu (mantido + [ALTERADO]: agora setamos estado)
        if re.fullmatch(r"menu", txt_norm, flags=re.IGNORECASE):
            actions.append(make_text_action(to, _menu_text(nome)))  # [ALTERADO] usa nome do contexto, se houver
            _set_state(sm, tenant, to, "awaiting_menu_selection")   # [NOVO]
            continue

        # 4) Disparo de template de teste (mantido)
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

        # [NOVO] 5) Tratamento da escolha do menu (somente se aguardando)
        if state == "awaiting_menu_selection" and re.fullmatch(r"[123]", txt_norm):
            _set_ctx(sm, tenant, to, {"menu_selected": txt_norm})

            if txt_norm == "1":
                actions.append(make_text_action(to, "Legal! Para começar, qual é o seu nome?"))
                _set_state(sm, tenant, to, "awaiting_name")
                continue

            if txt_norm == "2":
                actions.append(make_text_action(to, "Certo! Descreva brevemente o problema e mande anexo se quiser."))
                _set_state(sm, tenant, to, "awaiting_support_desc")
                continue

            if txt_norm == "3":
                actions.append(make_text_action(to, "Ok! Vou te conectar com uma pessoa da equipe. Aguarde um instante."))
                _set_state(sm, tenant, to, "escalated")
                _set_ctx(sm, tenant, to, {"handoff_requested": True})
                continue

        # [NOVO] 5.5) Confirmação do nome (state=awaiting_name_confirm)
        if state == "awaiting_name_confirm":
            # resposta afirmativa → usa profile_name como nome
            if YES_RE.match(txt_norm) and profile_name:
                _set_ctx(sm, tenant, to, {"nome": profile_name})
                _set_state(sm, tenant, to, "idle")
                actions.append(make_text_action(to, f"Perfeito, {profile_name}!"))
                actions.append(make_text_action(to, _menu_text(profile_name)))
                continue

            # se não foi "não" explícito e parece um nome, assume o nome dito
            if not NO_RE.match(txt_norm) and _looks_like_name(txt):
                nome_capturado = txt.strip().title()
                _set_ctx(sm, tenant, to, {"nome": nome_capturado})
                _set_state(sm, tenant, to, "idle")
                actions.append(make_text_action(to, f"Ótimo! Prazer, {nome_capturado}."))
                actions.append(make_text_action(to, _menu_text(nome_capturado)))
                continue

            # não entendeu → pede novamente
            actions.append(
                make_text_action(
                    to,
                    "Perdão, não entendi. Posso te chamar pelo nome que aparece no WhatsApp, "
                    f"{profile_name!s}? Se preferir, me diga como devo chamar você."
                )
            )
            # mantém awaiting_name_confirm
            continue

        # [NOVO] 6) Coleta de nome
        if state == "awaiting_name":
            nome_capturado = txt.strip().title()
            _set_ctx(sm, tenant, to, {"nome": nome_capturado})
            actions.append(make_text_action(to, f"Prazer, {nome_capturado}! Posso te ajudar com um orçamento."))  # mantém fluxo original
            # volta p/ idle e reoferece menu com nome
            _set_state(sm, tenant, to, "idle")
            actions.append(make_text_action(to, _menu_text(nome_capturado)))
            continue

        # [NOVO] 7) Descrição de suporte
        if state == "awaiting_support_desc":
            _set_ctx(sm, tenant, to, {"last_support_desc": txt})
            actions.append(make_text_action(to, "Obrigado! Registrei sua descrição. Em breve retornaremos."))
            _set_state(sm, tenant, to, "idle")
            actions.append(make_text_action(to, _menu_text(nome)))
            continue

        # 8) (Opcional) Atalho simples de agendamento (mantido como exemplo, sem estado)
        if re.search(r"\bagend(ar|o)\b", txt_norm):
            actions.append(make_text_action(to, "Aqui está o link para sugerir um horário: https://calendar.google.com/"))
            actions.append(make_text_action(to, "Quando concluir, me avise aqui que eu confirmo."))
            continue

        # 9) Fallback (mantido + [ALTERADO] com dica do menu)
        actions.append(make_text_action(to, "Recebi sua mensagem! Já te respondo. Digite 'menu' para ver opções."))

    return actions
