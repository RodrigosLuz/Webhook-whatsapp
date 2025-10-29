# app/flows/normalizer.py
"""
Normalização do payload do Webhook (WhatsApp Cloud API) para uma lista
de eventos simples e previsíveis.

Mantemos este módulo **puro** (sem dependências de Flask ou settings) para
facilitar testes unitários e reuso por automações de clientes.

Formato de saída (lista de dicts):
[
  {"from":"5561999999999","type":"text","text":"Oi"},
  {"from":"5561999999999","type":"image","id":"<media_id>","mime_type":"image/jpeg"},
  {"from":"5561999999999","type":"status","status":"read","msg_id":"wamid.XXX"}
]
"""

from __future__ import annotations

from typing import Any, Dict, List, Literal, TypedDict, NotRequired


# -----------------------------
# Tipos dos eventos normalizados
# -----------------------------
class BaseEvent(TypedDict):
    from_: str  # remetente/recipient_id (renomeado internamente para 'from' ao exportar)
    type: str


class TextEvent(BaseEvent):
    type: Literal["text"]
    text: str


class ImageEvent(BaseEvent):
    type: Literal["image"]
    id: NotRequired[str]
    mime_type: NotRequired[str]
    caption: NotRequired[str]


class AudioEvent(BaseEvent):
    type: Literal["audio"]
    id: NotRequired[str]
    mime_type: NotRequired[str]


class DocumentEvent(BaseEvent):
    type: Literal["document"]
    id: NotRequired[str]
    mime_type: NotRequired[str]
    filename: NotRequired[str]
    caption: NotRequired[str]


class LocationEvent(BaseEvent):
    type: Literal["location"]
    latitude: float
    longitude: float
    name: NotRequired[str]
    address: NotRequired[str]


class ButtonEvent(BaseEvent):
    type: Literal["button"]
    payload: str
    text: NotRequired[str]


class StatusEvent(BaseEvent):
    type: Literal["status"]
    status: Literal["sent", "delivered", "read", "failed"]
    msg_id: NotRequired[str]
    timestamp: NotRequired[str]


NormalizedEvent = Dict[str, Any]  # união dos tipos acima em tempo de execução


# -----------------------------
# Função principal
# -----------------------------
def normalize_incoming(body: Dict[str, Any]) -> List[NormalizedEvent]:
    """
    Converte o payload bruto do webhook Meta em uma lista de eventos simples.

    - Suporta mensagens de texto, imagem, áudio, documento, localização e
      cliques de botão (interações).
    - Suporta eventos de status (sent/delivered/read/failed).

    Observações:
    - Este parser é tolerante a campos ausentes (defensive parsing).
    - Não levanta exceções por campos faltantes; simplesmente ignora partes inválidas.
    """
    out: List[NormalizedEvent] = []

    for entry in _safe_list(body.get("entry")):
        for change in _safe_list(entry.get("changes")):
            value = _safe_dict(change.get("value"))

            # ------------------ mensagens (inbound) ------------------
            for m in _safe_list(value.get("messages")):
                from_ = str(m.get("from") or "")
                mtype = str(m.get("type") or "")
                if not from_ or not mtype:
                    continue

                if mtype == "text":
                    text_body = _safe_dict(m.get("text")).get("body", "")
                    evt: TextEvent = {"from_": from_, "type": "text", "text": str(text_body)}  # type: ignore[typeddict-item]
                    out.append(_export(evt))
                    continue

                if mtype == "image":
                    img = _safe_dict(m.get("image"))
                    evt: ImageEvent = {"from_": from_, "type": "image"}  # type: ignore[typeddict-item]
                    if img.get("id"):
                        evt["id"] = str(img["id"])
                    if img.get("mime_type"):
                        evt["mime_type"] = str(img["mime_type"])
                    if img.get("caption"):
                        evt["caption"] = str(img["caption"])
                    out.append(_export(evt))
                    continue

                if mtype == "audio":
                    aud = _safe_dict(m.get("audio"))
                    evt: AudioEvent = {"from_": from_, "type": "audio"}  # type: ignore[typeddict-item]
                    if aud.get("id"):
                        evt["id"] = str(aud["id"])
                    if aud.get("mime_type"):
                        evt["mime_type"] = str(aud["mime_type"])
                    out.append(_export(evt))
                    continue

                if mtype == "document":
                    doc = _safe_dict(m.get("document"))
                    evt: DocumentEvent = {"from_": from_, "type": "document"}  # type: ignore[typeddict-item]
                    if doc.get("id"):
                        evt["id"] = str(doc["id"])
                    if doc.get("mime_type"):
                        evt["mime_type"] = str(doc["mime_type"])
                    if doc.get("filename"):
                        evt["filename"] = str(doc["filename"])
                    if doc.get("caption"):
                        evt["caption"] = str(doc["caption"])
                    out.append(_export(evt))
                    continue

                if mtype == "location":
                    loc = _safe_dict(m.get("location"))
                    lat = loc.get("latitude")
                    lng = loc.get("longitude")
                    if lat is None or lng is None:
                        continue
                    evt: LocationEvent = {  # type: ignore[typeddict-item]
                        "from_": from_,
                        "type": "location",
                        "latitude": float(lat),
                        "longitude": float(lng),
                    }
                    if loc.get("name"):
                        evt["name"] = str(loc["name"])
                    if loc.get("address"):
                        evt["address"] = str(loc["address"])
                    out.append(_export(evt))
                    continue

                # Interações (botões) — button / interactive
                if mtype == "button":
                    btn = _safe_dict(m.get("button"))
                    payload = btn.get("payload")
                    if payload is None:
                        continue
                    evt: ButtonEvent = {  # type: ignore[typeddict-item]
                        "from_": from_,
                        "type": "button",
                        "payload": str(payload),
                    }
                    if btn.get("text"):
                        evt["text"] = str(btn["text"])
                    out.append(_export(evt))
                    continue

                # Outros tipos podem ser adicionados aqui (sticker, contacts, etc.)
                out.append({"from": from_, "type": mtype})

            # ------------------ status (delivery/conversation) ------------------
            for st in _safe_list(value.get("statuses")):
                recipient = str(st.get("recipient_id") or "")
                status = str(st.get("status") or "")
                if not recipient or not status:
                    continue
                evt: StatusEvent = {  # type: ignore[typeddict-item]
                    "from_": recipient,
                    "type": "status",
                    "status": status,  # sent, delivered, read, failed
                }
                if st.get("id"):
                    evt["msg_id"] = str(st["id"])
                if st.get("timestamp"):
                    evt["timestamp"] = str(st["timestamp"])
                out.append(_export(evt))

    return out


# -----------------------------
# Helpers internos
# -----------------------------
def _safe_list(x: Any) -> list:
    return x if isinstance(x, list) else []


def _safe_dict(x: Any) -> dict:
    return x if isinstance(x, dict) else {}


def _export(evt: BaseEvent | NormalizedEvent) -> NormalizedEvent:
    """
    Converte a chave interna 'from_' para 'from' antes de devolver o evento.
    Mantemos 'from_' apenas para evitar conflito com palavra reservada em alguns linters.
    Perfis de tipo (TypedDict) são usados só para ajuda estática; em runtime é dict.
    """
    if isinstance(evt, dict) and "from_" in evt:
        evt = dict(evt)  # copia rasa
        evt["from"] = evt.pop("from_")
    return evt  # type: ignore[return-value]
