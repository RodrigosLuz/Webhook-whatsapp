# tests/integration/test_webhook_incoming.py
"""
Testes de integração para o endpoint principal do webhook (/).
"""

from tests.factories.event_factory import (
    make_incoming_text_payload,
    make_status_read_payload,
)


def test_webhook_receives_text_and_returns_200(client):
    """
    Simula o recebimento de uma mensagem de texto "Oi".
    O app deve processar, gerar uma resposta (DRY_RUN) e retornar 200.
    """
    payload = make_incoming_text_payload(from_number="5561999999999", text="Oi")
    resp = client.post("/", json=payload)

    # Sempre responde 200 (mesmo em erro) — comportamento intencional
    assert resp.status_code == 200


def test_webhook_receives_status_and_logs_ok(client):
    """
    Simula o recebimento de um evento de status 'read'.
    O app deve processar e responder 200.
    """
    payload = make_status_read_payload(recipient_id="5561999999999")
    resp = client.post("/", json=payload)
    assert resp.status_code == 200


def test_webhook_verify_token_ok(client, app):
    """
    Simula a verificação do webhook via GET / (Meta)
    com token correto.
    """
    token = app.config["VERIFY_TOKEN"]
    resp = client.get(
        "/",
        query_string={
            "hub.mode": "subscribe",
            "hub.challenge": "12345",
            "hub.verify_token": token,
        },
    )
    assert resp.status_code == 200
    assert resp.data.decode() == "12345"


def test_webhook_verify_token_invalid(client):
    """
    Simula verificação com token inválido → deve retornar 403.
    """
    resp = client.get(
        "/",
        query_string={
            "hub.mode": "subscribe",
            "hub.challenge": "12345",
            "hub.verify_token": "token_errado",
        },
    )
    assert resp.status_code == 403
