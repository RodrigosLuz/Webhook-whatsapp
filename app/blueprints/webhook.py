# app/blueprints/webhook.py
from __future__ import annotations

import json
import uuid
from flask import Blueprint, request, jsonify, current_app

from app.logging import get_logger
from app.flows.normalizer import normalize_incoming
from app.flows.router import decide_responses, mask_phone
from app.wa.client import send_text, send_template
from app.tenants import registry

from app.models import (
    insert_message,
    update_message_status_by_external_id,
    add_processed_id,
    has_processed_id,
    iso_now,
)
logger = get_logger(__name__)
webhook = Blueprint("webhook", __name__)

def _get_phone_number_id_from_payload(body: dict) -> str | None:
    try:
        entry0 = (body.get("entry") or [None])[0] or {}
        change0 = (entry0.get("changes") or [None])[0] or {}
        value = change0.get("value") or {}
        metadata = value.get("metadata") or {}
        return metadata.get("phone_number_id")
    except Exception:
        return None
    
def _extract_contact_names(body: dict) -> dict[str, str]:
    """
    Varre o payload e retorna { wa_id: profile_name } para contatos presentes.
    """
    mapping: dict[str, str] = {}
    try:
        entry0 = (body.get("entry") or [None])[0] or {}
        change0 = (entry0.get("changes") or [None])[0] or {}
        value = change0.get("value") or {}
        for c in value.get("contacts") or []:
            wa_id = str(c.get("wa_id") or "")
            name = ((c.get("profile") or {}).get("name") or "").strip()
            if wa_id and name:
                mapping[wa_id] = name
    except Exception:
        pass
    return mapping

def _log_statuses_and_persist(change_value: dict, db_path: str) -> None:
    statuses = change_value.get("statuses")
    if not isinstance(statuses, list):
        return

    for st in statuses:
        base = {
            "status": st.get("status"),
            "msg_id": st.get("id"),
            "to": mask_phone(st.get("recipient_id")),
            "timestamp": st.get("timestamp"),
        }
        errs = st.get("errors")

        # Dedupe por msg_id (se existir):
        msg_id = st.get("id")
        if msg_id and has_processed_id(db_path, msg_id):
            logger.info("delivery.duplicate_status", extra=base)
        else:
            # atualiza status da mensagem outbound (se existir)
            if msg_id and st.get("status"):
                update_message_status_by_external_id(db_path, msg_id, st["status"])
                add_processed_id(db_path, msg_id)

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

@webhook.get("/")
def verify():
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

@webhook.post("/")
def receive():
    body = request.get_json(silent=True) or {}
    try:
        raw_size = len(json.dumps(body, ensure_ascii=False).encode("utf-8"))
    except Exception:
        raw_size = 0

    logger.info("webhook.incoming", extra={"has_entry": isinstance(body.get("entry"), list), "raw_size": raw_size})
    logger.debug("webhook.body", extra={"body": body})

    db_path = current_app.config.get("SQLITE_PATH", "data/app.db")
    sm = current_app.config.get("SESSION_MANAGER")

    try:
        # 1) Normaliza
        events = normalize_incoming(body)
        logger.debug("webhook.events", extra={"count": len(events), "preview": events[:3]})

        # 2) Resolve tenant
        pnid = _get_phone_number_id_from_payload(body)
        tenant_respond = registry.resolve(pnid, current_app.config)

        # Extrai nomes de contatos (se houver)
        name_map = _extract_contact_names(body)

        # 2.1 Persistir inbound (apenas mensagens de usuário; statuses são tratados depois)
        for e in events:
            if e.get("type") == "text":
                # cria/atualiza sessão
                if sm:
                    sm.touch(phone=str(e.get("from","")), tenant=str(pnid or "unknown"))

                    to = str(e.get("from",""))
                    meta_name = name_map.get(to)
                    if meta_name:
                        # tenta assinatura nova (tenant+phone); cai para a antiga (phone) se necessário
                        try:
                            sess = sm.get(tenant=str(pnid or "unknown"), phone=to)
                        except TypeError:
                            sess = sm.get(to) if hasattr(sm, "get") else None

                        ctx = (sess or {}).get("context") or {}
                        if not ctx.get("nome"):  # não sobrescreve nome já confirmado pelo usuário
                            try:
                                sm.set_context(tenant=str(pnid or "unknown"), phone=to,
                                               updates={"profile_name": meta_name})
                            except TypeError:
                                sm.set_context(to, {"profile_name": meta_name})
                                
                # grava inbound
                insert_message(
                    db_path,
                    id=str(uuid.uuid4()),
                    tenant_id=str(pnid or "unknown"),
                    phone=str(e.get("from","")),
                    direction="inbound",
                    text=str(e.get("text") or ""),
                    raw_payload=None,
                    status=None,
                    attachments_meta=None,
                    external_msg_id=None,  # inbound geralmente não traz wamid utilizável aqui
                    created_at=iso_now(),
                )

        # 3) Executa automação
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

        # 4) Envia e persiste outbound
        for a in actions:
            to = a.get("to")
            if not to:
                continue
            try:
                if "template" in a:
                    res = send_template(to, a["template"], phone_number_id=pnid)
                    kind = "template"
                else:
                    res = send_text(to, a.get("text", ""), phone_number_id=pnid)
                    kind = "text"

                # tenta capturar wamid do retorno real
                ext_id = None
                try:
                    msgs = (res or {}).get("messages") or []
                    if msgs and isinstance(msgs, list) and msgs[0].get("id"):
                        ext_id = msgs[0]["id"]
                except Exception:
                    ext_id = None

                insert_message(
                    db_path,
                    id=str(uuid.uuid4()),
                    tenant_id=str(pnid or "unknown"),
                    phone=str(to),
                    direction="outbound",
                    text=a.get("text") if "text" in a else None,
                    attachments_meta=a.get("template") if "template" in a else None,  # apenas para registro
                    external_msg_id=ext_id,
                    status="sent" if not (res or {}).get("dry_run") else None,
                    raw_payload=(res if not (res or {}).get("dry_run") else None),
                    created_at=iso_now(),
                )

                logger.info(
                    "msg.out",
                    extra={
                        "to": mask_phone(to),
                        "kind": kind,
                        "has_external_id": bool(ext_id),
                        "dry_run": bool(current_app.config.get("DRY_RUN", False)),
                    },
                )
            except Exception as e:
                logger.exception(
                    "msg.out_error",
                    extra={"to": mask_phone(a.get("to")), "kind": ("template" if "template" in a else "text"), "error": str(e)},
                )
                # mesmo com erro, seguimos para as próximas ações

        # 5) Statuses (delivery/read/failed) — log + atualizar tabela
        try:
            entry0 = (body.get("entry") or [None])[0] or {}
            change0 = (entry0.get("changes") or [None])[0] or {}
            value = change0.get("value") or {}
            _log_statuses_and_persist(value, db_path)
        except Exception:
            pass

        # 6) Limpeza rápida de sessões expiradas (best effort)
        try:
            if sm:
                removed = sm.cleanup_expired()
                if removed:
                    logger.info("sessions.cleanup", extra={"removed": removed})
        except Exception:
            pass

        return ("", 200)

    except Exception as e:
        logger.exception("webhook.handler_error", extra={"message": str(e)})
        return ("", 200)
