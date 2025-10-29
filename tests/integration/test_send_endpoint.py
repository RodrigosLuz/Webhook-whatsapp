# tests/integration/test_send_endpoint.py
"""
Testes de integração para o endpoint /send.
"""

import pytest


def test_send_text_success(client):
    """
    Envia uma mensagem de texto válida (modo DRY_RUN ativado).
    Espera retorno 200 com ok=True.
    """
    payload = {"to": "5561999999999", "text": "Olá mundo!"}
    resp = client.post("/send", json=payload)

    assert resp.status_code == 200
    data = resp.get_json()
    assert data["ok"] is True
    assert "result" in data
    assert data["result"]["dry_run"] is True


def test_send_template_success(client):
    """
    Envia uma mensagem de template válida.
    """
    payload = {
        "to": "5561999999999",
        "template": {"name": "hello_world", "language": {"code": "en_US"}},
    }
    resp = client.post("/send", json=payload)

    assert resp.status_code == 200
    data = resp.get_json()
    assert data["ok"] is True
    assert "result" in data


@pytest.mark.parametrize(
    "payload,expected_error",
    [
        ({}, "Informe \"to\""),
        ({"to": "5561999999999"}, "Informe \"text\" ou \"template\""),
    ],
)
def test_send_missing_fields(client, payload, expected_error):
    """
    Verifica mensagens de erro ao faltar campos obrigatórios.
    """
    resp = client.post("/send", json=payload)
    assert resp.status_code == 400
    data = resp.get_json()
    assert expected_error in data["error"]
