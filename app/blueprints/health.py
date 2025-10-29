# app/blueprints/health.py
"""
Blueprint simples de healthcheck e status do ambiente.
Usado por Render, Railway, etc. para verificar se o app está ativo.
"""

from flask import Blueprint, jsonify, current_app

health = Blueprint("health", __name__)


@health.get("/health")
def get_health():
    """
    Retorna um JSON básico com informações do ambiente atual.
    - ok: True -> app está rodando
    - env: nome do ambiente (dev/hom/prod)
    - dry_run: indica se está em modo simulação
    - version: versão do Graph API em uso
    """
    cfg = current_app.config
    return jsonify(
        {
            "ok": True,
            "env": cfg.get("CONFIG_NAME", "dev"),
            "dry_run": bool(cfg.get("DRY_RUN", False)),
            "graph_version": cfg.get("GRAPH_VERSION", "v22.0"),
        }
    )
