# app/blueprints/webhook.py
"""
Webhook do WhatsApp Cloud API.

- GET /       -> verificação do webhook (Meta/Facebook)
- POST /      -> recepção de eventos (mensagens e status)
  * Normaliza o payload em eventos simples
  * Resolve automação por cliente (tenant) via tenants.registry.resolve
    (usa mapeamento TENANT_REGISTRY em app.config e/ou TENANT_REGISTRY_JSON)
  * Gera ações (decide_responses / tenant.respond)
  * Envia mensagens (respeitando DRY_RUN) e loga status/erros
"""

from __future__ import annotations

import json
from flask import Blueprint, request, jsonify, current_app

from app.logging import get_logger
from app.flows.normalizer import normalize_incoming
from app.flows.router import decide_responses, mask_phone  # mask_phone usado nos logs
from app.wa.client import send_text, send_template  # template pode ser usado por automações
from app.tenants import registry  # <- usar o resolver centralizado

webhook = Blueprint("webhook", __name__)
logger = get_logger(__name__)


# -----------------------------------------------------------
# Helpers locais
# -----------------------------------------------------------
def _get_phone_number_id_from_payload(body: dict) -> str | None:
    """
    Tenta extrair o phone_number_id do payload da Cloud API.
    """
    try:
        entry0 = (body.get("entry") or [None])[0] or {}
        change0 = (entry0.get("changes") or [None])[0] or {}
        value = change0.get("value") or {}
        metadata = value.get("metadata") or {}
        return metadata.get("phone_number_id")
    except Exception:
        return None


def _log_statuses(change_value: dict) -> None:
    """
    Reproduz logs úteis de status (sent/delivered/read/failed) incluindo conversation/pricing.
    """
    statuses = change_value.get("statuses")
    if not isinstance(statuses, list):
        return

    for st in statuses:
        base = {
            "status": st.get("status"),  # sent, delivered, read, failed...
            "msg_id": st.get("id"),
            "to": mask_phone(st.get("recipient_id")),
            "timestamp": st.get("timestamp"),
        }
        errs = st.get("errors")
        if isinstance(errs, list) and errs:
            logger.error(
                "delivery.status_failed",
                extra={
                    **base,
                    "errors": [
                        {"code": e.get("code"), "title": e.get("title"), "details": e.get("details")}
                        for e in errs
                    ],
                },
            )
        else:
            logger.info(
                "delivery.status",
                extra={**base, "conversation": st.get("conversation"), "pricing": st.get("pricing")},
            )


# -----------------------------------------------------------
# GET / -> verificação do webhook (Meta)
# -----------------------------------------------------------
@webhook.get("/")
def verify():
    """
    Endpoint de verificação do webhook (chamado pelo Meta com GET):
    - Lê hub.mode, hub.challenge e hub.verify_token
    - Confere se mode == 'subscribe' e token bate com VERIFY_TOKEN
    - Se ok, retorna o challenge (200); se não, 403.
    - Se não for verificação (faltam params), devolve 'ok'
    """
    cfg = current_app.config
    mode = request.args.get("hub.mode")
    challenge = request.args.get("hub.challenge")
    token = request.args.get("hub.verify_token")

    if mode and challenge and token:
        ok = (mode == "subscribe") and (token == cfg.get("VERIFY_TOKEN"))
        logger.info("webhook.verify", extra={"mode": mode, "ok": ok})
        if ok:
            return challenge, 200
        return ("", 403)

    return ("ok", 200)


# -----------------------------------------------------------
# POST / -> recepção do webhook
# -----------------------------------------------------------
@webhook.post("/")
def receive():
    """
    Recebe eventos do WhatsApp, normaliza, decide respostas e envia (text/template).
    Responde sempre 200 para evitar retries infinitos do Meta.
    """
    body = request.get_json(silent=True) or {}
    try:
        raw_size = len(json.dumps(body, ensure_ascii=False).encode("utf-8"))
    except Exception:
        raw_size = 0

    logger.info(
        "webhook.incoming",
        extra={
            "has_entry": isinstance(body.get("entry"), list),
            "raw_size": raw_size,
        },
    )
    logger.debug("webhook.body", extra={"body": body})

    try:
        # 1) Normaliza -> eventos
        events = normalize_incoming(body)
        logger.debug("webhook.events", extra={"count": len(events), "preview": events[:3]})

        # 2) Resolve tenant via registry (centralizado)
        pnid = _get_phone_number_id_from_payload(body)
        tenant_respond = registry.resolve(pnid, current_app.config)

        if tenant_respond:
            actions = tenant_respond(events, settings=current_app.config)
            source = "tenant"
        else:
            actions = decide_responses(events)
            source = "default"

        logger.info(
            "webhook.decisions",
            extra={
                "source": source,
                "actions": [
                    {"to": mask_phone(a.get("to")), "type": ("template" if "template" in a else "text")}
                    for a in actions
                ],
            },
        )

        # 3) Executa -> envia (CORREÇÃO: isolar exceções por ação para não abortar o lote)
        for a in actions:
            try:
                if "template" in a:
                    res = send_template(a["to"], a["template"], phone_number_id=pnid)
                    kind = "template"
                else:
                    res = send_text(a["to"], a.get("text", ""), phone_number_id=pnid)
                    kind = "text"

                logger.info(
                    "msg.out",
                    extra={
                        "to": mask_phone(a["to"]),
                        "kind": kind,
                        "api_result_preview": str(res)[:200],
                        "dry_run": bool(current_app.config.get("DRY_RUN", False)),
                    },
                )
            except Exception as e:
                logger.exception(
                    "msg.out_error",
                    extra={
                        "to": mask_phone(a.get("to")),
                        "kind": ("template" if "template" in a else "text"),
                        "error": str(e),
                        "dry_run": bool(current_app.config.get("DRY_RUN", False)),
                    },
                )
                # Continua para as próximas ações

        # 4) Logs específicos de status/entrega (se presentes no payload)
        try:
            entry0 = (body.get("entry") or [None])[0] or {}
            change0 = (entry0.get("changes") or [None])[0] or {}
            value = change0.get("value") or {}
            _log_statuses(value)
        except Exception:
            pass

        return ("", 200)

    except Exception as e:
        logger.exception("webhook.handler_error", extra={"message": str(e)})
        # Mesmo em erro, respondemos 200 para evitar retry em loop.
        return ("", 200)
