# app/blueprints/outbound.py
"""
Blueprint para envios proativos (endpoint /send).
Permite ao backend iniciar mensagens via API, respeitando DRY_RUN.
"""

from flask import Blueprint, request, jsonify, current_app
import requests
from app.wa.client import send_text, send_template
from app.logging import get_logger
from app.flows.router import mask_phone

outbound = Blueprint("outbound", __name__)
logger = get_logger(__name__)


@outbound.post("/send")
def send():
    """
    POST /send
    Corpo esperado:
    {
      "to": "5561999999999",
      "text": "Olá!"             # OU
      "template": { "name": "...", "language": {"code": "pt_BR"} }
    }

    - Valida parâmetros mínimos
    - Escolhe o modo (texto/template)
    - Executa envio (respeitando DRY_RUN)
    - Retorna resultado JSON
    """
    secret = current_app.config.get("INTERNAL_SEND_TOKEN")
    auth = request.headers.get("X-Internal-Token")
    if secret and auth != secret:
        return jsonify({"error": "unauthorized"}), 401

    cfg = current_app.config
    dry_run = bool(cfg.get("DRY_RUN", False))

    try:
        data = request.get_json(silent=True) or {}
        to = data.get("to")
        text = data.get("text")
        template = data.get("template")

        if not to:
            # CORREÇÃO: evitar logar o body inteiro para não vazar PII/conteúdo
            logger.warning(
                "send.missing_to",
                extra={
                    "has_text": bool(text),
                    "has_template": bool(template),
                },
            )
            return jsonify({"error": 'Informe "to"'}), 400

        # CORREÇÃO: rejeitar quando ambos text e template forem enviados
        if text and template:
            logger.warning(
                "send.both_text_and_template",
                extra={"to": mask_phone(to), "dry_run": dry_run},
            )
            return jsonify({"error": 'Envie apenas um de: "text" OU "template"'}), 400

        if not text and not template:
            logger.warning("send.missing_content", extra={"to": mask_phone(to)})
            return jsonify({"error": 'Informe "text" ou "template"'}), 400

        mode = "text" if text else "template"
        logger.info(
            "send.request",
            extra={
                "to": mask_phone(to),
                "mode": mode,
                "template_name": (template or {}).get("name"),
                "dry_run": dry_run,
            },
        )

        result = send_text(to, text) if text else send_template(to, template)
        logger.info("send.success", extra={"to": mask_phone(to)})

        return jsonify({"ok": True, "result": result})
    except requests.HTTPError as e:
        logger.error("send.error_http", extra={"message": str(e)})
        return jsonify({"error": str(e)}), 502
    except Exception as e:
        logger.exception("send.error_generic", extra={"message": str(e)})
        return jsonify({"error": str(e)}), 500
