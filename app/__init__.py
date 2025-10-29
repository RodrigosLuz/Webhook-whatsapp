# app/__init__.py
"""
Fábrica principal do Flask App.

- Cria e configura a instância do Flask.
- Carrega configurações do ambiente (via app.settings).
- Inicializa logging.
- Garante SQLite pronto (data/app.db).
- Registra blueprints (webhook/outbound/health/dev_simulator/panel_api).
"""

from __future__ import annotations

from flask import Flask
from app.settings import load_settings
from app.logging import configure_logging, get_logger
from app.models import ensure_db
from app.sessions import SessionManager

def create_app(config_name: str | None = None) -> Flask:
    app = Flask(__name__, template_folder="templates")

    # 1) Config
    settings = load_settings(config_name)
    app.config.update(settings)

    # 2) Logging
    configure_logging(app.config.get("LOG_LEVEL", "INFO"))
    log = get_logger(__name__)
    log.info("app.init", extra={"env": app.config.get("CONFIG_NAME", "dev")})

    # 3) SQLite (garante arquivo e tabelas)
    app.config.setdefault("SQLITE_PATH", "data/app.db")
    ensure_db(app.config["SQLITE_PATH"])
    log.info("db.ready", extra={"path": app.config["SQLITE_PATH"]})

    # 4) Session Manager (in-memory)
    app.config["SESSION_MANAGER"] = SessionManager()

    # 5) Blueprints
    from app.blueprints.webhook import webhook
    from app.blueprints.outbound import outbound
    from app.blueprints.health import health
    from app.blueprints.dev_simulator import dev_simulator
    from app.blueprints.panel_api import panel_api

    app.register_blueprint(webhook)
    app.register_blueprint(outbound)
    app.register_blueprint(health)
    app.register_blueprint(dev_simulator)
    app.register_blueprint(panel_api)

    return app
