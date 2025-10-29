# tests/factories/event_factory.py
"""
Factories/helpers para montar payloads de webhook da WhatsApp Cloud API
para uso nos testes (unitários e de integração).

Objetivos:
- Evitar JSONs repetidos e verbosos dentro dos testes
- Gerar payloads mínimos porém válidos para os parsers/rotas
"""

from __future__ import annotations

from typing import Any, Dict, List, Optional
from datetime import datetime, timezone
import uuid


# -------------------------------------------------------------------
# Utils básicos
# -------------------------------------------------------------------
def now_unix() -> str:
    """Retorna timestamp unix (string) em segundos."""
    return str(int(datetime.now(timezone.utc).timestamp()))


def _gen_id(prefix: str = "wamid") -> str:
    """Gera um id fake parecido com wamid.* apenas para testes."""
    return f"{prefix}.{uuid.uuid4().hex[:8]}"


# -------------------------------------------------------------------
# Peças de mensagens
# -------------------------------------------------------------------
def make_text_message(from_number: str, text: str, msg_id: Optional[str] = None) -> Dict[str, Any]:
    """
    Mensagem de TEXTO mínima.
    """
    return {
        "from": from_number,
        "id": msg_id or _gen_id(),
        "timestamp": now_unix(),
        "type": "text",
        "text": {"body": text},
    }


def make_image_message(
    from_number: str,
    media_id: str | None = None,
    mime: str | None = "image/jpeg",
    caption: str | None = None,
    msg_id: Optional[str] = None,
) -> Dict[str, Any]:
    """
    Mensagem de IMAGEM mínima.
    """
    data: Dict[str, Any] = {
        "from": from_number,
        "id": msg_id or _gen_id(),
        "timestamp": now_unix(),
        "type": "image",
        "image": {},
    }
    if media_id:
        data["image"]["id"] = media_id
    if mime:
        data["image"]["mime_type"] = mime
    if caption:
        data["image"]["caption"] = caption
    return data


def make_location_message(
    from_number: str,
    latitude: float,
    longitude: float,
    name: str | None = None,
    address: str | None = None,
    msg_id: Optional[str] = None,
) -> Dict[str, Any]:
    """
    Mensagem de LOCALIZAÇÃO mínima.
    """
    data: Dict[str, Any] = {
        "from": from_number,
        "id": msg_id or _gen_id(),
        "timestamp": now_unix(),
        "type": "location",
        "location": {"latitude": latitude, "longitude": longitude},
    }
    if name:
        data["location"]["name"] = name
    if address:
        data["location"]["address"] = address
    return data


def make_button_message(from_number: str, payload: str, text: str | None = None) -> Dict[str, Any]:
    """
    Evento de clique em BOTÃO (simplificado).
    """
    data: Dict[str, Any] = {
        "from": from_number,
        "id": _gen_id(),
        "timestamp": now_unix(),
        "type": "button",
        "button": {"payload": payload},
    }
    if text:
        data["button"]["text"] = text
    return data


# -------------------------------------------------------------------
# Peças de status
# -------------------------------------------------------------------
def make_status(
    recipient_id: str,
    status: str = "read",  # sent|delivered|read|failed
    msg_id: Optional[str] = None,
    conversation_id: Optional[str] = None,
    pricing_model: Optional[str] = None,  # ex.: "CBP"
    pricing_category: Optional[str] = None,  # ex.: "marketing" | "utility"
    error: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    """
    Evento de STATUS mínimo.
    """
    data: Dict[str, Any] = {
        "id": msg_id or _gen_id(),
        "recipient_id": recipient_id,
        "status": status,
        "timestamp": now_unix(),
    }
    if conversation_id:
        data["conversation"] = {"id": conversation_id, "origin": {"type": "business_initiated"}}
    if pricing_model or pricing_category:
        data["pricing"] = {}
        if pricing_model:
            data["pricing"]["pricing_model"] = pricing_model
        if pricing_category:
            data["pricing"]["category"] = pricing_category
    if error:
        data["errors"] = [error]
    return data


# -------------------------------------------------------------------
# Envelope do webhook (o "body" que o Flask recebe)
# -------------------------------------------------------------------
def make_webhook_body(
    messages: Optional[List[Dict[str, Any]]] = None,
    statuses: Optional[List[Dict[str, Any]]] = None,
    phone_number_id: str = "879357005252665",
    display_phone_number: str = "+55 61 99999-9999",
    waba_id: str = "24838169579210572",
) -> Dict[str, Any]:
    """
    Monta o body completo no formato esperado pelo webhook:
    {
      "object": "whatsapp_business_account",
      "entry": [
        {
          "id": "<waba_id>",
          "changes": [
            {
              "value": {
                "messaging_product": "whatsapp",
                "metadata": {
                  "display_phone_number": "...",
                  "phone_number_id": "..."
                },
                "messages": [...],
                "statuses": [...]
              },
              "field": "messages"
            }
          ]
        }
      ]
    }
    """
    value: Dict[str, Any] = {
        "messaging_product": "whatsapp",
        "metadata": {
            "display_phone_number": display_phone_number,
            "phone_number_id": phone_number_id,
        },
    }
    if messages:
        value["messages"] = messages
    if statuses:
        value["statuses"] = statuses

    return {
        "object": "whatsapp_business_account",
        "entry": [
            {
                "id": waba_id,
                "changes": [
                    {
                        "value": value,
                        "field": "messages",
                    }
                ],
            }
        ],
    }


# -------------------------------------------------------------------
# Atalhos "prontos para uso" nos testes
# -------------------------------------------------------------------
def make_incoming_text_payload(
    from_number: str,
    text: str,
    phone_number_id: str = "879357005252665",
) -> Dict[str, Any]:
    """
    Retorna um payload completo com UMA mensagem de texto.
    """
    msg = make_text_message(from_number, text)
    return make_webhook_body(messages=[msg], phone_number_id=phone_number_id)


def make_status_read_payload(
    recipient_id: str,
    msg_id: Optional[str] = None,
    phone_number_id: str = "879357005252665",
) -> Dict[str, Any]:
    """
    Retorna um payload completo com UM status 'read'.
    """
    st = make_status(recipient_id=recipient_id, status="read", msg_id=msg_id)
    return make_webhook_body(statuses=[st], phone_number_id=phone_number_id)
