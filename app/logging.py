# app/logging.py
"""
Logger estruturado simples para o projeto.

Características:
- Saída em JSON (ideal para plataformas como Render, Railway, Fly.io etc.)
- Campos padrão: timestamp (UTC), nível, mensagem e extras
- Usa logging padrão do Python, sem dependências externas
- Integra-se facilmente com o Flask (via configure_logging)
"""

from __future__ import annotations

import json
import logging
from datetime import datetime, timezone
from typing import Any, Dict


# -------------------------------------------------------
# Helpers internos
# -------------------------------------------------------
def _now_iso() -> str:
    return (
        datetime.now(timezone.utc)
        .isoformat(timespec="milliseconds")
        .replace("+00:00", "Z")
    )


class JsonFormatter(logging.Formatter):
    """
    Formata mensagens de log em JSON estruturado.
    """
    _skip = {
        "name","msg","args","levelname","levelno","pathname","filename","module",
        "exc_info","exc_text","stack_info","lineno","funcName","created","msecs",
        "relativeCreated","thread","threadName","processName","process","message"
    }

    def format(self, record: logging.LogRecord) -> str:
        base = {
            "ts": _now_iso(),
            "level": record.levelname,
            "msg": record.getMessage(),
            "logger": record.name,
        }
        # inclui quaisquer atributos extras que vieram via extra={...}
        for k, v in record.__dict__.items():
            if k not in self._skip and not k.startswith("_"):
                base[k] = v
        return json.dumps(base, ensure_ascii=False)


# -------------------------------------------------------
# Configuração global
# -------------------------------------------------------
def configure_logging(level: str = "INFO") -> None:
    """
    Configura o logger raiz do Python para usar formato JSON.
    Deve ser chamado uma única vez na inicialização do app.
    """
    root = logging.getLogger()
    root.setLevel(level.upper())

    handler = logging.StreamHandler()
    handler.setFormatter(JsonFormatter())

    # Remove handlers antigos e aplica o novo
    root.handlers.clear()
    root.addHandler(handler)


def get_logger(name: str | None = None) -> logging.Logger:
    """
    Retorna um logger configurado com o formato JSON.
    """
    return logging.getLogger(name or "app")
