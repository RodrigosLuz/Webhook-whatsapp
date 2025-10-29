# app/__init__.py
"""
Fábrica principal do Flask App.

Responsabilidades:
- Criar e configurar a instância do Flask.
- Carregar configurações do ambiente (via app.settings).
- Registrar blueprints (rotas e automações básicas).
- Inicializar componentes globais (logger, HTTP client, etc.).
"""

from __future__ import annotations

from flask import Flask
from app.settings import load_settings
from app.logging import configure_logging


def create_app(config_name: str | None = None) -> Flask:
    """
    Cria e retorna uma instância configurada do Flask App.

    Args:
        config_name: nome do ambiente (ex.: "dev", "hom", "prod").
                     Se None, usa variável de ambiente CONFIG_NAME ou "dev".

    Returns:
        Flask: app pronto para rodar.
    """
    app = Flask(__name__)

    # === 1) Configurações do ambiente ===
    settings = load_settings(config_name)
    app.config.update(settings)

    # === 2) Logger global ===
    configure_logging(app.config.get("LOG_LEVEL", "INFO"))

    # === 3) Registro dos blueprints ===
    from app.blueprints.webhook import webhook
    from app.blueprints.outbound import outbound
    from app.blueprints.health import health

    app.register_blueprint(webhook)
    app.register_blueprint(outbound)
    app.register_blueprint(health)


    if settings.get('CONFIG_NAME') == 'dev':
        from app.blueprints.dev_simulator import dev_simulator
        app.register_blueprint(dev_simulator)

    # === 4) Configuração opcional: TENANT_REGISTRY ===
    # Pode ser preenchida em app.tenants.registry ou via .env (TENANT_REGISTRY_JSON)
    from app.tenants import registry
    app.config["TENANT_REGISTRY"] = registry._merge_registry(app.config)

    return app
