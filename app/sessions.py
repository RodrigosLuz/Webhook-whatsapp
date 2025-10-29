# app/sessions.py
from __future__ import annotations
from typing import Any, Dict, Optional, Tuple
from datetime import datetime, timedelta, timezone
import uuid

def now_utc() -> datetime:
    return datetime.now(timezone.utc)

def iso(dt: datetime) -> str:
    return dt.isoformat(timespec="milliseconds").replace("+00:00", "Z")

DEFAULT_TTLS = {
    "idle": 60 * 60,
    "awaiting_menu_selection": 5 * 60,
    "awaiting_name": 20 * 60,
    "awaiting_name_confirm": 10 * 60,  # [NOVO] confirmação rápida
    "awaiting_email": 20 * 60,
    "booking_pending": 24 * 60 * 60,
    "escalated": 12 * 60 * 60,
    "closed": 5 * 60,
}

class SessionManager:
    def __init__(self, ttls: Optional[Dict[str, int]] = None):
        # chave: (tenant, phone)
        self._sessions: Dict[Tuple[str, str], Dict[str, Any]] = {}
        self._ttls = dict(DEFAULT_TTLS)
        if ttls:
            self._ttls.update(ttls)

    def _exp_for_state(self, state: str) -> datetime:
        ttl = self._ttls.get(state, self._ttls["idle"])
        return now_utc() + timedelta(seconds=int(ttl))

    def _key(self, tenant: str, phone: str) -> Tuple[str, str]:
        # Se quiser, normalize aqui (ex.: só dígitos do phone)
        return (str(tenant), str(phone))

    def get(self, *, tenant: str, phone: str) -> Optional[Dict[str, Any]]:
        return self._sessions.get(self._key(tenant, phone))

    def touch(self, *, tenant: str, phone: str, default_state: str = "idle") -> Dict[str, Any]:
        k = self._key(tenant, phone)
        s = self._sessions.get(k)
        if not s:
            s = {
                "session_id": str(uuid.uuid4()),
                "tenant": tenant,
                "phone": phone,
                "state": default_state,
                "context": {},
                "last_activity": iso(now_utc()),
                "expires_at": iso(self._exp_for_state(default_state)),
                "attempts": 0,
                "locked_by_operator": None,
            }
            self._sessions[k] = s
            return s
        # update activity
        s["last_activity"] = iso(now_utc())
        return s

    def set_state(self, *, tenant: str, phone: str, state: str) -> None:
        k = self._key(tenant, phone)
        s = self._sessions.get(k)
        if not s:
            return
        s["state"] = state
        s["expires_at"] = iso(self._exp_for_state(state))
        s["last_activity"] = iso(now_utc())

    def set_context(self, *, tenant: str, phone: str, updates: Dict[str, Any]) -> None:
        k = self._key(tenant, phone)
        s = self._sessions.get(k)
        if not s:
            return
        ctx = s.get("context") or {}
        ctx.update(updates)
        s["context"] = ctx
        s["last_activity"] = iso(now_utc())

    def cleanup_expired(self) -> int:
        now = now_utc()
        victims = [
            k for k, s in self._sessions.items()
            if datetime.fromisoformat(s["expires_at"].replace("Z", "+00:00")) <= now
        ]
        for k in victims:
            self._sessions.pop(k, None)
        return len(victims)

    def snapshot(self) -> Dict[str, Dict[str, Any]]:
        # cópia rasa p/ debug/inspeção
        return dict(self._sessions)

