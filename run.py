 # app.py
"""
Ponto de entrada simples para desenvolvimento.

- Carrega o .env específico do ambiente (ex.: .env.dev, .env.hom, .env.prod)
- Cria o app via factory (create_app)
- Lê configurações SOMENTE de app.config (nada de variáveis "mágicas" globais)
- Faz um log de inicialização em JSON com informações úteis
- Sobe o servidor embutido do Flask (para produção, use gunicorn/uvicorn apontando para 'app:create_app()')
"""

from __future__ import annotations

import os
import json
from datetime import datetime, timezone
from pathlib import Path

from dotenv import load_dotenv
from app import create_app

from app.flows.router import mask_phone as _mask_phone


# -------------------------------
# Helpers locais só para o startup
# -------------------------------
def _now_iso() -> str:
    return (
        datetime.now(timezone.utc)
        .isoformat(timespec="milliseconds")
        .replace("+00:00", "Z")
    )


def _redact(s: str | None) -> str | None:
    if not s:
        return s
    s = str(s)
    return s[:6] + "…redacted" if len(s) > 20 else s


def _json_log(level: str, msg: str, extra: dict | None = None) -> None:
    payload = {"ts": _now_iso(), "level": level.upper(), "msg": msg}
    if extra:
        payload.update(extra)
    print(json.dumps(payload, ensure_ascii=False), flush=True)


# -------------------------------
# Boot
# -------------------------------
# Ambiente (dev/hom/prod)
CONFIG_NAME = os.environ.get("CONFIG_NAME", "dev")

# Carrega .env.<env> se existir (ex.: .env.dev). Não falha se o arquivo não existir.
env_file = Path(f".env.{CONFIG_NAME}")
if env_file.exists():
    load_dotenv(env_file.as_posix(), override=True)
else:
    # Carrega um .env “genérico”, caso exista, como fallback
    load_dotenv(override=False)

# Cria o app com a config do ambiente
app = create_app(CONFIG_NAME)

if __name__ == "__main__":
    cfg = app.config  # Fonte única da verdade para as configs

    # Coleta infos para log de inicialização
    port = int(cfg.get("PORT", 3000))
    verify_token = cfg.get("VERIFY_TOKEN")
    wa_token = cfg.get("WHATSAPP_TOKEN")
    phone_number_id = cfg.get("PHONE_NUMBER_ID")
    graph_version = cfg.get("GRAPH_VERSION", "v22.0")
    dry_run = bool(cfg.get("DRY_RUN", False))
    log_level = (cfg.get("LOG_LEVEL", "INFO") or "INFO").upper()

    _json_log(
        "INFO",
        "server.start",
        {
            "env": CONFIG_NAME,
            "port": port,
            "python": os.sys.version.split()[0],
            "graph_version": graph_version,
            "phoneNumberId": _mask_phone(phone_number_id),
            "verifyToken_set": bool(verify_token),
            "waToken_set": bool(wa_token),
            "dry_run": dry_run,
            "log_level": log_level,
        },
    )

    # Aviso sutil se tokens não estiverem presentes
    if not wa_token or not verify_token or not phone_number_id:
        _json_log(
            "WARN",
            "config.incomplete",
            {
                "hint": "Verifique WHATSAPP_TOKEN, VERIFY_TOKEN e PHONE_NUMBER_ID no .env do ambiente.",
                "waToken_preview": _redact(wa_token),
                "verifyToken_preview": _redact(verify_token),
                "phoneNumberId_preview": _mask_phone(phone_number_id),
            },
        )

    # Servidor de desenvolvimento
    app.run(host="0.0.0.0", port=port)
