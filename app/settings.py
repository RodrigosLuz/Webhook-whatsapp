# app/settings.py
"""
Carrega e organiza todas as configurações do app.

- Lê variáveis de ambiente (.env.<env>) usando dotenv
- Monta um dicionário simples com todas as chaves relevantes
- Define valores padrão quando necessário
- Evita múltiplos load_dotenv (feito apenas aqui)

Uso:
    from app.settings import load_settings
    settings = load_settings("dev")
"""

from __future__ import annotations

import os
from pathlib import Path
from dotenv import load_dotenv


# -----------------------------------------------------------
# Função principal
# -----------------------------------------------------------
def load_settings(env_name: str | None = None) -> dict:
    """
    Carrega as variáveis de ambiente para o app Flask.
    Retorna um dicionário pronto para app.config.update().
    """
    config_name = env_name or os.getenv("CONFIG_NAME", "dev")
    env_file = Path(f".env.{config_name}")

    # Carrega o arquivo de ambiente (se existir)
    if env_file.exists():
        load_dotenv(env_file.as_posix(), override=True)
    else:
        # Fallback: tenta .env genérico se existir
        generic_env = Path(".env")
        if generic_env.exists():
            load_dotenv(generic_env.as_posix(), override=False)

    # ---- GERA CONFIGURAÇÃO ----
    dry_run_flag = os.getenv("DRY_RUN", "0").strip() == "1"

    settings = {
        # Identificação
        "CONFIG_NAME": config_name,

        # Servidor
        "PORT": int(os.getenv("PORT", "3000")),
        "LOG_LEVEL": (os.getenv("LOG_LEVEL", "DEBUG" if dry_run_flag else "INFO")).upper(),

        # Meta / WhatsApp Cloud API
        "VERIFY_TOKEN": os.getenv("VERIFY_TOKEN"),
        "WHATSAPP_TOKEN": os.getenv("WHATSAPP_TOKEN"),
        "PHONE_NUMBER_ID": os.getenv("PHONE_NUMBER_ID"),
        "GRAPH_VERSION": os.getenv("GRAPH_VERSION", "v22.0"),

        # Modo de execução
        "DRY_RUN": dry_run_flag,

        # Testes / fallback
        "PHONE_NUMBER_TEST": os.getenv("PHONE_NUMBER_TEST", "61988887766"),
        "PHONE_NUMBER_ID_TEST": os.getenv("PHONE_NUMBER_ID_TEST", "666666666666666"),

        # Segurança de /send (token interno opcional)
        "INTERNAL_SEND_TOKEN": os.getenv("INTERNAL_SEND_TOKEN"),
    }

    # Registry opcional em JSON (pode ser carregado depois em tenants/registry)
    registry_json = os.getenv("TENANT_REGISTRY_JSON")
    if registry_json:
        import json

        try:
            settings["TENANT_REGISTRY"] = json.loads(registry_json)
        except Exception:
            settings["TENANT_REGISTRY"] = {}

    settings.setdefault("SQLITE_PATH", "data/app.db")

    return settings
