# app/http.py
"""
Módulo utilitário para requisições HTTP (baseado em requests.Session).

Oferece uma sessão compartilhada com:
- retry/backoff para erros temporários (429, 5xx)
- timeout padrão (com possibilidade de override por chamada)
- log de requisições
- integração fácil com app.wa.client
"""

from __future__ import annotations

import time
import uuid
from typing import Any, Dict, Optional
import requests
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry

from app.logging import get_logger

logger = get_logger(__name__)


class HttpClient:
    """
    Cliente HTTP com sessão persistente e retry básico.
    """

    def __init__(
        self,
        base_url: Optional[str] = None,
        timeout: int = 30,
        max_retries: int = 3,
        backoff_factor: float = 0.5,
    ):
        self.base_url = base_url or ""
        self.timeout = timeout

        self.session = requests.Session()
        retries = Retry(
            total=max_retries,
            backoff_factor=backoff_factor,
            status_forcelist=[429, 500, 502, 503, 504],
            allowed_methods={"GET", "POST", "PUT", "DELETE", "PATCH"},
            respect_retry_after_header=True,  # respeita Retry-After
        )
        adapter = HTTPAdapter(max_retries=retries)
        self.session.mount("http://", adapter)
        self.session.mount("https://", adapter)

    def request(self, method: str, path: str, **kwargs) -> requests.Response:
        """
        Executa uma requisição HTTP com logs e tempo de execução.
        Permite override de timeout por chamada via kwargs['timeout'].
        """
        url = path if path.startswith("http") else f"{self.base_url.rstrip('/')}/{path.lstrip('/')}"
        rid = str(uuid.uuid4())
        started = time.perf_counter()

        try:
            logger.debug("http.request", extra={"rid": rid, "method": method, "url": url})
            timeout = kwargs.pop("timeout", self.timeout)  # <-- override por chamada
            resp = self.session.request(method, url, timeout=timeout, **kwargs)
            elapsed_ms = int((time.perf_counter() - started) * 1000)
            logger.info(
                "http.response",
                extra={
                    "rid": rid,
                    "status": resp.status_code,
                    "elapsed_ms": elapsed_ms,
                    "snippet": resp.text[:200],
                },
            )
            return resp
        except requests.RequestException as e:
            logger.exception("http.error", extra={"rid": rid, "url": url, "error": str(e)})
            raise

    def get_json(self, path: str, **kwargs) -> Dict[str, Any]:
        """
        Faz GET e retorna JSON, com log estruturado.
        """
        resp = self.request("GET", path, **kwargs)
        try:
            return resp.json()
        except Exception:
            return {}

    def post_json(self, path: str, payload: Dict[str, Any], **kwargs) -> Dict[str, Any]:
        """
        Faz POST com corpo JSON e retorna JSON, com log estruturado.
        """
        headers = kwargs.pop("headers", {})
        headers.setdefault("Accept", "application/json")

        resp = self.request("POST", path, headers=headers, json=payload, **kwargs)
        try:
            return resp.json()
        except Exception:
            return {}


# Instância padrão global (pode ser usada diretamente)
http_client = HttpClient()
