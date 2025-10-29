# app/wa/client.py
"""
Cliente para integração com a WhatsApp Cloud API.

Responsável por enviar mensagens (texto ou template) à Graph API.
Respeita o modo DRY_RUN (não envia requisições reais).

Principais funções públicas:
- send_text(to, body)
- send_template(to, template)

Uso interno:
- wa_post(payload)  → chamada genérica à Graph API (com log, timeout, tratamento de erro)
"""

from __future__ import annotations

import json
import uuid
import time
import requests
from flask import current_app

from app.flows.router import mask_phone
from app.logging import get_logger

logger = get_logger(__name__)


# -------------------------------------------------------------
# Função principal de POST para a Graph API
# -------------------------------------------------------------
def wa_post(payload: dict, phone_number_id: str | None = None) -> dict:
    """
    Envia um POST à Graph API (WhatsApp Cloud API).

    - Monta a URL com GRAPH_VERSION e PHONE_NUMBER_ID
    - Usa token WHATSAPP_TOKEN
    - Respeita modo DRY_RUN (não envia de fato)
    - Loga requisição e resposta em JSON estruturado
    """
    cfg = current_app.config
    pnid = phone_number_id or cfg.get("PHONE_NUMBER_ID")
    whatsapp_token = cfg.get("WHATSAPP_TOKEN")
    if not pnid or not whatsapp_token:
        logger.error("wa.misconfig", extra={"have_pnid": bool(pnid), "have_token": bool(whatsapp_token)})
        raise RuntimeError("WhatsApp API misconfigured: PHONE_NUMBER_ID/WHATSAPP_TOKEN ausentes.")
    
    graph_version = cfg.get("GRAPH_VERSION", "v22.0")
    dry_run = bool(cfg.get("DRY_RUN", False))

    url = f"https://graph.facebook.com/{graph_version}/{pnid}/messages"

    if dry_run:
        logger.info(
            "wa.dry_run",
            extra={
                "url": url,
                "to": mask_phone(payload.get("to")),
                "type": payload.get("type"),
                "payload_preview": str(payload)[:200],
            },
        )
        return {"dry_run": True, "payload": payload}

    # Modo real
    rid = str(uuid.uuid4())
    started = time.perf_counter()

    headers = {
        "Authorization": f"Bearer {whatsapp_token}",
        "Content-Type": "application/json",
    }

    try:
        logger.debug(
            "wa.request",
            extra={
                "rid": rid,
                "url": url,
                "to": mask_phone(payload.get("to")),
                "type": payload.get("type"),
            },
        )

        resp = requests.post(url, headers=headers, json=payload, timeout=30)
        elapsed_ms = int((time.perf_counter() - started) * 1000)
        snippet = (resp.text[:300] + ("…" if len(resp.text) > 300 else ""))

        logger.info(
            "wa.response",
            extra={
                "rid": rid,
                "status": resp.status_code,
                "elapsed_ms": elapsed_ms,
                "snippet": snippet,
            },
        )

        if not resp.ok:
            try:
                detail = resp.json()
            except Exception:
                detail = {"raw": resp.text}
            logger.error(
                "wa.error",
                extra={"rid": rid, "status": resp.status_code, "detail": detail},
            )
            resp.raise_for_status()

        try:
            return resp.json()
        except Exception:
            return {}

    except requests.RequestException as e:
        logger.exception("wa.network_error", extra={"rid": rid, "error": str(e)})
        raise


# -------------------------------------------------------------
# Funções públicas de envio
# -------------------------------------------------------------
def send_text(to: str, body: str, phone_number_id: str | None = None) -> dict:
    """
    Envia mensagem de texto simples via WhatsApp Cloud API (ou simula se DRY_RUN=True).
    """
    payload = {
        "messaging_product": "whatsapp",
        "to": to,
        "type": "text",
        "text": {"body": body},
    }
    return wa_post(payload, phone_number_id)


def send_template(to: str, template: dict, phone_number_id: str | None = None) -> dict:
    """
    Envia mensagem de template (pré-aprovado) via WhatsApp Cloud API (ou simula se DRY_RUN=True).
    """
    payload = {
        "messaging_product": "whatsapp",
        "to": to,
        "type": "template",
        "template": template,
    }
    return wa_post(payload, phone_number_id)
