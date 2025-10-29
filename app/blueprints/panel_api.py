# app/blueprints/panel_api.py
from __future__ import annotations
from flask import Blueprint, request, jsonify, current_app
from app.models import list_messages_by_phone, list_recent_contacts

panel_api = Blueprint("panel_api", __name__)

@panel_api.get("/panel/api/messages")
def api_messages():
    phone = request.args.get("phone")
    if not phone:
        return jsonify({"error": "param 'phone' é obrigatório"}), 400
    limit = int(request.args.get("limit", "50"))
    before = request.args.get("before")
    db_path = current_app.config.get("SQLITE_PATH", "data/app.db")
    rows = list_messages_by_phone(db_path, phone, limit=limit, before=before)
    return jsonify({"ok": True, "items": rows})

@panel_api.get("/panel/api/contacts/recent")
def api_contacts_recent():
    limit = int(request.args.get("limit", "50"))
    db_path = current_app.config.get("SQLITE_PATH", "data/app.db")
    rows = list_recent_contacts(db_path, limit=limit)
    return jsonify({"ok": True, "items": rows})
