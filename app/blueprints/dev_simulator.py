# app/blueprints/dev_simulator.py
from __future__ import annotations

import json
import time
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from flask import Blueprint, Response, current_app, jsonify, render_template, request

from app.flows.normalizer import normalize_incoming
from app.tenants import registry
from app.flows.router import decide_responses
from app.models import list_messages_by_phone

dev_simulator = Blueprint("dev_simulator", __name__, template_folder=None)

_history: List[Dict[str, Any]] = []  # legado (mantido para testes rápidos)


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="milliseconds").replace("+00:00", "Z")


def _get_pnid_from_payload(body: Dict[str, Any]) -> Optional[str]:
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
    # NÃO carrega histórico nem conecta automaticamente — o front cuida disso
    return render_template("dev_simchat.html")


@dev_simulator.post("/dev/simulate")
def run_simulation():
    """
    Simula a automação SEM chamar o webhook real.
    Aceita:
      - body no formato da Meta (com entry/changes/...)
      - ou { "phone_number_id": "...", "from": "55...", "text": "..." }
    Retorna as 'actions' que seriam geradas.
    """
    body = request.get_json(silent=True) or {}
    if "entry" in body:
        payload = body
    else:
        payload = {
            "entry": [
                {
                    "changes": [
                        {
                            "value": {
                                "messaging_product": "whatsapp",
                                "messages": [
                                    {
                                        "from": body.get("from"),
                                        "type": "text",
                                        "text": {"body": body.get("text", "")},
                                    }
                                ],
                                "metadata": {"phone_number_id": body.get("phone_number_id")},
                            }
                        }
                    ]
                }
            ]
        }

    events = normalize_incoming(payload)
    pnid = _get_pnid_from_payload(payload)

    tenant_fn = registry.resolve(pnid, current_app.config) if pnid else None
    if tenant_fn:
        actions = tenant_fn(events, settings=current_app.config)
        source = "tenant"
    else:
        actions = decide_responses(events)
        source = "default"

    # guardamos no histórico dev só para debug/inspeção
    _history.append(
        {
            "id": len(_history) + 1,
            "ts": _now_iso(),
            "inbound_payload": payload,
            "events": events,
            "source": source,
            "actions": actions,
        }
    )
    return jsonify({"ok": True, "source": source, "actions": actions})


@dev_simulator.get("/dev/history")
def get_history():
    recent = list(reversed(_history))[:200]
    return jsonify({"ok": True, "count": len(_history), "recent": recent})


# --------- API de mensagens para a UI (histórico) ---------
@dev_simulator.get("/dev/messages")
def list_messages_api():
    """
    Retorna mensagens do SQLite para o par (pnid, phone).
    Nota: o storage expõe busca por phone DESC; aqui filtramos por tenant e devolvemos ASC.
    """
    pnid = request.args.get("pnid", "").strip()
    phone = request.args.get("phone", "").strip()
    limit = int(request.args.get("limit", "150") or 150)

    if not phone:
        return jsonify({"messages": []})

    db_path = current_app.config.get("SQLITE_PATH", "data/app.db")
    rows = list_messages_by_phone(db_path, phone, limit=limit)  # DESC
    # filtra por tenant se informado
    if pnid:
        rows = [r for r in rows if str(r.get("tenant_id")) == str(pnid)]
    # devolve ASC
    rows = list(reversed(rows))
    return jsonify({"messages": rows})


# --------- Stream "tipo SSE" por polling leve ----------
@dev_simulator.get("/dev/stream")
def stream_messages():
    """
    Stream server-sent events simples, por polling.
    Envia lotes de mensagens novas (baseado em created_at) para o par (pnid, phone).
    Não envia histórico: só o que chegar DEPOIS da conexão.
    """
    pnid = request.args.get("pnid", "").strip()
    phone = request.args.get("phone", "").strip()
    if not phone:
        return Response("missing phone", status=400)

    db_path = current_app.config.get("SQLITE_PATH", "data/app.db")
    last_seen = _now_iso()  # só o que chegar depois da conexão

    def gen():
        nonlocal last_seen
        yield "retry: 1500\n\n"  # sugere reconexão de 1.5s
        while True:
            try:
                rows = list_messages_by_phone(db_path, phone, limit=200)  # DESC
                if pnid:
                    rows = [r for r in rows if str(r.get("tenant_id")) == str(pnid)]
                rows = list(reversed(rows))  # ASC

                fresh = [r for r in rows if r.get("created_at", "") > last_seen]
                if fresh:
                    last_seen = fresh[-1]["created_at"]
                    yield f"data: {json.dumps(fresh, ensure_ascii=False)}\n\n"
            except Exception:
                # em caso de erro silencioso, evita travar o gerador
                pass
            time.sleep(0.8)

    return Response(gen(), mimetype="text/event-stream")
