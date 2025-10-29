# app/tenants/registry.py
"""
Registry (bem simples) para automações de clientes (tenants).

Objetivo:
- Mapear `phone_number_id` -> módulo Python com função `respond(events, settings)`.
- Permitir configuração por código **e** por ambiente (via variável TENANT_REGISTRY_JSON).

Como usar:
1) Mapeie estático aqui em `REGISTRY` (exemplo abaixo).
2) OU defina a env `TENANT_REGISTRY_JSON` com um JSON do tipo:
     {"879357005252665": "app.tenants.cliente_x", "444444444444444": "app.tenants.default"}

Em runtime:
- `resolve(phone_number_id, app_config)` devolve uma função `respond(events, settings)` ou None.
"""

from __future__ import annotations

import os
import json
import importlib
from typing import Callable, Dict, Optional, Any


# -------------------------------
# Mapeamento estático (opcional)
# Preencha conforme necessário:
#   REGISTRY["<PHONE_NUMBER_ID>"] = "app.tenants.cliente_x"
# -------------------------------
# Devo colocar abaixo os registros dos clientes, caso queira definir estaticamente. Mas como padrão vou definir em .env.*
REGISTRY: Dict[str, str] = {
    # "879357005252665": "app.tenants.cliente_x",
    # "444444444444444": "app.tenants.default",
}


def _load_from_env() -> Dict[str, str]:
    """
    Carrega mapeamento da variável de ambiente TENANT_REGISTRY_JSON, se existir.
    Valor esperado: JSON dict { "<phone_number_id>": "<module.path>" }
    """
    raw = os.getenv("TENANT_REGISTRY_JSON", "").strip()
    if not raw:
        return {}
    try:
        data = json.loads(raw)
        return data if isinstance(data, dict) else {}
    except Exception:
        return {}


def _merge_registry(app_config: Dict[str, Any] | None = None) -> Dict[str, str]:
    """
    Consolida o registry a partir de:
      1) REGISTRY (estático neste arquivo)
      2) app_config.get("TENANT_REGISTRY") (opcional, ex.: definido no create_app)
      3) TENANT_REGISTRY_JSON (env, JSON)

    Ordem de precedência (maior -> menor):
      app_config > env JSON > REGISTRY
    """
    merged: Dict[str, str] = {}
    merged.update(REGISTRY)

    env_map = _load_from_env()
    if env_map:
        merged.update(env_map)

    if app_config:
        cfg_map = app_config.get("TENANT_REGISTRY") or {}
        if isinstance(cfg_map, dict):
            merged.update(cfg_map)

    return merged


def _import_respond(module_path: str) -> Optional[Callable[[list, dict], list]]:
    """
    Importa o módulo e retorna a função `respond` se existir e for chamável.
    """
    try:
        mod = importlib.import_module(module_path)
        fn = getattr(mod, "respond", None)
        return fn if callable(fn) else None
    except Exception:
        return None


def resolve(phone_number_id: Optional[str], app_config: Dict[str, Any] | None = None) -> Optional[Callable[[list, dict], list]]:
    """
    Dado um `phone_number_id`, retorna a função `respond(events, settings)` do tenant
    correspondente, se houver. Caso contrário, retorna None.

    Exemplo:
        fn = resolve("879357005252665", current_app.config)
        actions = fn(events, settings=current_app.config)  # se fn não for None
    """
    if not phone_number_id:
        return None

    registry = _merge_registry(app_config)
    module_path = registry.get(str(phone_number_id))
    if not module_path:
        return None

    return _import_respond(module_path)
