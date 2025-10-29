# tests/unit/test_normalizer.py
"""
Testes unitários para o módulo app.flows.normalizer.
Garante que o payload da Meta é convertido corretamente em eventos simples.
"""

from app.flows.normalizer import normalize_incoming
from tests.factories import event_factory as f


def test_normalize_single_text_message():
    payload = f.make_incoming_text_payload(from_number="5561999999999", text="Oi")
    events = normalize_incoming(payload)

    assert isinstance(events, list)
    assert len(events) == 1
    evt = events[0]
    assert evt["type"] == "text"
    assert evt["text"] == "Oi"
    assert evt["from"].startswith("5561")


def test_normalize_status_read():
    payload = f.make_status_read_payload(recipient_id="5561999999999")
    events = normalize_incoming(payload)

    assert isinstance(events, list)
    assert len(events) == 1
    evt = events[0]
    assert evt["type"] == "status"
    assert evt["status"] == "read"
    assert evt["from"] == "5561999999999"


def test_normalize_ignores_invalid_entries():
    """
    Payload sem mensagens nem statuses → deve retornar lista vazia.
    """
    payload = {"entry": [{"changes": [{"value": {}}]}]}
    events = normalize_incoming(payload)
    assert events == []
