# app/blueprints/dev_simulator.py
from flask import Blueprint, render_template, request, jsonify, current_app
from typing import List, Dict, Any
from datetime import datetime
from app.flows.normalizer import normalize_incoming
from app.tenants import registry
from app.flows.router import decide_responses

dev_simulator = Blueprint("dev_simulator", __name__, template_folder=None)

# Histórico em memória (dev only)
# cada item: {id, ts, inbound: {...}, actions: [...], source}
_history: List[Dict[str, Any]] = []


def _get_phone_number_id_from_payload(body: Dict[str, Any]) -> str | None:
    try:
        entry0 = (body.get("entry") or [None])[0] or {}
        change0 = (entry0.get("changes") or [None])[0] or {}
        value = change0.get("value") or {}
        metadata = value.get("metadata") or {}
        return metadata.get("phone_number_id")
    except Exception:
        return None


@dev_simulator.get("/dev/simchat")
def simchat_page():
    """Página com o formulário simples e a área de chat."""
    return render_template("dev_simchat.html")


@dev_simulator.post("/dev/simulate")
def run_simulation():
    """
    Espera JSON com EITHER:
    - um payload completo (igual ao webhook) no body
    OR
    - um json simples: {"phone_number_id": "...", "from": "...", "text": "..."}
    """
    body = request.get_json(silent=True) or {}
    # Se body já contém mensagens no formato do webhook -> usa direto
    if "entry" in body:
        payload = body
    else:
        # Constrói payload simples
        phone_number_id = body.get("phone_number_id") or request.form.get("phone_number_id")
        from_num = body.get("from") or request.form.get("from")
        text = body.get("text") or request.form.get("text", "")
        payload = {
            "entry": [
                {
                    "changes": [
                        {
                            "value": {
                                "messaging_product": "whatsapp",
                                "messages": [{"from": from_num, "type": "text", "text": {"body": text}}],
                                "metadata": {"phone_number_id": phone_number_id},
                            }
                        }
                    ]
                }
            ]
        }

    # Normaliza o payload para eventos (usa sua função existente)
    events = normalize_incoming(payload)

    # Descobre phone_number_id (tenta extrair do payload)
    pnid = _get_phone_number_id_from_payload(payload)

    # Resolve tenant
    tenant_fn = registry.resolve(pnid, current_app.config) if pnid else None

    if tenant_fn:
        # chama a automação do tenant (pode gerar ações)
        actions = tenant_fn(events, settings=current_app.config)
        source = "tenant"
    else:
        # fallback para respostas simples / router
        actions = decide_responses(events)
        source = "default"

    # Armazena no histórico (dev)
    entry = {
        "id": len(_history) + 1,
        "ts": datetime.utcnow().isoformat() + "Z",
        "inbound_payload": payload,
        "events": events,
        "source": source,
        "actions": actions,
    }
    _history.append(entry)

    # Retorna ações e id do histórico
    return jsonify({"ok": True, "entry_id": entry["id"], "source": source, "actions": actions})


@dev_simulator.get("/dev/history")
def get_history():
    """Retorna o histórico (mais recente primeiro)."""
    # limitar para evitar payload gigantesco (dev)
    recent = list(reversed(_history))[:200]
    return jsonify({"ok": True, "count": len(_history), "recent": recent})
