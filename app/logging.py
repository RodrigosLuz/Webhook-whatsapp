# app/logging.py
"""
Logger estruturado simples para o projeto.

Objetivo:
- Produzir logs JSON enxutos.
- Quando houver exceção, incluir apenas a parte curta que aponta
  o frame relevante (arquivo, linha, função) e a mensagem do erro,
  no campo "exc_short".
- Evitar imprimir o traceback completo por padrão.
"""

from __future__ import annotations

import json
import logging
import os
import traceback
import linecache
import re
from datetime import datetime, timezone
from typing import Any, Dict

# -------------------------
# Helpers
# -------------------------
def _now_iso() -> str:
    return (
        datetime.now(timezone.utc)
        .isoformat(timespec="milliseconds")
        .replace("+00:00", "Z")
    )

# chaves do LogRecord que não devemos clonar para o JSON
_RESERVED_KEYS = {
    "name","msg","args","levelname","levelno","pathname","filename","module",
    "exc_info","exc_text","stack_info","lineno","funcName","created","msecs",
    "relativeCreated","thread","threadName","processName","process","message"
}

_FRAME_REGEX = re.compile(r'  File "([^"]+)", line (\d+), in (\S+)')

# -------------------------
# Formatter
# -------------------------
class JsonFormatter(logging.Formatter):
    """
    JsonFormatter que produz um JSON enxuto:
    - ts, level, msg, logger (básicos)
    - quaisquer extras passados via extra={...} (exceto chaves reservadas)
    - exc_short: quando há exceção, uma versão curta apontando o frame relevante
    """

    def _choose_relevant_frame(self, frames: list[tuple[str, int, str]] | None):
        """
        Recebe lista de (filename, lineno, funcname) na ordem do traceback.
        Heurística:
         - prefere frames cujo filename comece com cwd e que não estejam em site-packages
         - senão escolhe o último frame disponível
        """
        if not frames:
            return None
        cwd = os.getcwd()
        for fname, lineno, funcname in reversed(frames):
            if fname and fname.startswith(cwd) and "site-packages" not in fname and "/lib/python" not in fname:
                return (fname, lineno, funcname)
        for fname, lineno, funcname in reversed(frames):
            if fname and "site-packages" not in fname and "/lib/python" not in fname:
                return (fname, lineno, funcname)
        # fallback
        fname, lineno, funcname = frames[-1]
        return (fname, lineno, funcname)

    def _format_short_from_frame(self, filename: str, lineno: int, funcname: str, exc_type_name: str, exc_value_str: str):
        """
        Monta a string curta:
        File "path", line N, in func
            <code line>
              ^^^^
        ErrorType: message
        """
        try:
            line = linecache.getline(filename, lineno).rstrip("\n")
            if not line:
                return f'File "{filename}", line {lineno}, in {funcname}\n    <source not available>\n{exc_type_name}: {exc_value_str}'

            # tenta identificar o nome alvo (p.ex. name 'xxxx' is not defined)
            caret_line = ""
            m_name = re.search(r"name '([^']+)' is not defined", exc_value_str)
            if m_name:
                name = m_name.group(1)
                idx = line.find(name)
                if idx != -1:
                    caret_line = " " * (4 + idx) + "^" * len(name)

            # tenta padrão comum de attribute error
            if not caret_line:
                m_attr = re.search(r"attribute '([^']+)'", exc_value_str)
                if m_attr:
                    name = m_attr.group(1)
                    idx = line.find(name)
                    if idx != -1:
                        caret_line = " " * (4 + idx) + "^" * len(name)

            short = f'File "{filename}", line {lineno}, in {funcname}\n'
            short += f'    {line}\n'
            if caret_line:
                short += f'{caret_line}\n'
            short += f'{exc_type_name}: {exc_value_str}'
            return short
        except Exception:
            return None

    def _parse_traceback_string(self, tb_str: str):
        """
        Extrai frames de uma string de traceback (quando alguém passou traceback.format_exc()).
        Retorna lista de (filename, lineno, funcname).
        """
        frames = []
        try:
            for m in _FRAME_REGEX.finditer(tb_str):
                fname, lineno, funcname = m.group(1), int(m.group(2)), m.group(3)
                frames.append((fname, lineno, funcname))
        except Exception:
            pass
        return frames

    def _try_build_from_exc_string(self, record: logging.LogRecord):
        """
        Tenta gerar exc_short a partir de record.__dict__['exc'] (string formatted).
        """
        try:
            exc_str = record.__dict__.get("exc")
            if not exc_str or not isinstance(exc_str, str):
                return None
            frames = self._parse_traceback_string(exc_str)
            if not frames:
                return None
            chosen = self._choose_relevant_frame(frames)
            if not chosen:
                return None
            fname, lineno, funcname = chosen
            last_line = exc_str.rstrip("\n").splitlines()[-1]
            if ":" in last_line:
                exc_type_name, exc_value_str = last_line.split(":", 1)
                exc_type_name = exc_type_name.strip()
                exc_value_str = exc_value_str.strip()
            else:
                exc_type_name = "Error"
                exc_value_str = last_line.strip()
            return self._format_short_from_frame(fname, lineno, funcname, exc_type_name, exc_value_str)
        except Exception:
            return None

    def _try_build_from_exc_info(self, exc_type, exc_value, tb):
        """
        Gera exc_short a partir de exc_info (objeto).
        """
        try:
            extracted = traceback.extract_tb(tb)
            frames = [(fr.filename, fr.lineno, fr.name) for fr in extracted]
            chosen = self._choose_relevant_frame(frames)
            if not chosen:
                return None
            fname, lineno, funcname = chosen
            exc_type_name = getattr(exc_type, "__name__", str(exc_type))
            exc_value_str = str(exc_value)
            return self._format_short_from_frame(fname, lineno, funcname, exc_type_name, exc_value_str)
        except Exception:
            return None

    def format(self, record: logging.LogRecord) -> str:
        base: Dict[str, Any] = {
            "ts": _now_iso(),
            "level": record.levelname,
            "msg": record.getMessage(),
            "logger": record.name,
        }

        # inclui extras (exceto chaves reservadas)
        for k, v in record.__dict__.items():
            if k in _RESERVED_KEYS:
                continue
            if k.startswith("_"):
                continue
            base[k] = v

        # Gera exc_short quando for possível — não incluímos o traceback completo por padrão
        try:
            # 1) prefer exc_info (objeto)
            if record.exc_info:
                try:
                    exc_type, exc_value, tb = record.exc_info
                    short = self._try_build_from_exc_info(exc_type, exc_value, tb)
                    if short:
                        base["exc_short"] = short
                except Exception:
                    # não quebrar o logger por causa do formatter
                    base["exc_in_formatter_error"] = True

            else:
                # 2) se não houver exc_info, mas algum código passou a string 'exc' via extra, tente parsear
                short = self._try_build_from_exc_string(record)
                if short:
                    base["exc_short"] = short
        except Exception:
            base["exc_in_formatter_error"] = True

        return json.dumps(base, ensure_ascii=False)


# -------------------------
# Config global
# -------------------------
def configure_logging(level: str = "INFO") -> None:
    """
    Configura o logger raiz do Python para usar JsonFormatter.
    Deve ser chamado uma única vez na inicialização do app.
    """
    root = logging.getLogger()
    root.setLevel(level.upper())

    handler = logging.StreamHandler()
    handler.setFormatter(JsonFormatter())

    root.handlers.clear()
    root.addHandler(handler)

    # confirmação no startup para facilitar debug de bootstrap
    logging.getLogger(__name__).info("logging configured: JsonFormatter active")


def get_logger(name: str | None = None) -> logging.Logger:
    """
    Retorna um logger (wrapper simples).
    """
    return logging.getLogger(name or "app")
