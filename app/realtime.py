# app/realtime.py
from __future__ import annotations

import json
import threading
import queue
import time
from typing import Dict, List

# Canal = "pnid|phone"
def channel_key(pnid: str, phone: str) -> str:
    return f"{pnid}|{phone}"

class _Broadcaster:
    def __init__(self) -> None:
        self._subs: Dict[str, List[queue.Queue]] = {}
        self._lock = threading.Lock()

    def publish(self, channel: str, payload: dict) -> None:
        data = f"data: {json.dumps(payload, ensure_ascii=False)}\n\n"
        with self._lock:
            queues = list(self._subs.get(channel, []))
        for q in queues:
            try:
                q.put_nowait(data)
            except queue.Full:
                pass

    def subscribe(self, channel: str):
        q: queue.Queue = queue.Queue(maxsize=1000)
        with self._lock:
            self._subs.setdefault(channel, []).append(q)

        # primeiro “retry” para reconectar rápido se cair
        yield "retry: 1000\n\n"

        try:
            # heartbeats a cada 25s para manter conexões vivas
            last_hb = time.time()
            while True:
                try:
                    item = q.get(timeout=2.0)
                    yield item
                except queue.Empty:
                    if time.time() - last_hb > 25:
                        last_hb = time.time()
                        yield "event: ping\ndata: {}\n\n"
        finally:
            with self._lock:
                lst = self._subs.get(channel)
                if lst and q in lst:
                    lst.remove(q)

broadcaster = _Broadcaster()
