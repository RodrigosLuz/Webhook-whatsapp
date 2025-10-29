# tests/unit/test_router.py
"""
Testes unitários para o módulo app.flows.router.
Verifica as regras padrão de roteamento/decisão.
"""

from app.flows.router import decide_responses, make_text_action, make_template_action


def _make_text_event(from_number: str, text: str) -> dict:
    return {"from": from_number, "type": "text", "text": text}


def test_greeting_rules():
    events = [
        _make_text_event("5561999999999", "oi"),
        _make_text_event("5561999999999", "olá"),
        _make_text_event("5561999999999", "ola"),
    ]
    actions = decide_responses(events)

    assert len(actions) == 3
    # Todos devem ser mensagens de texto
    assert all(("text" in a and "to" in a) for a in actions)


def test_schedule_rule():
    events = [
        _make_text_event("5561999999999", "Qual é o horário?"),
        _make_text_event("5561999999999", "horario de atendimento"),
    ]
    actions = decide_responses(events)

    assert len(actions) == 2
    assert all("text" in a for a in actions)
    assert "9h às 18h" in actions[0]["text"]


def test_menu_rule():
    events = [_make_text_event("5561999999999", "menu")]
    actions = decide_responses(events)

    assert len(actions) == 1
    assert "Menu" in actions[0]["text"]


def test_template_trigger():
    events = [_make_text_event("5561999999999", "template hello")]
    actions = decide_responses(events)

    assert len(actions) == 1
    a = actions[0]
    assert "template" in a
    assert a["template"]["name"] == "hello_world"
    assert a["template"]["language"]["code"] == "en_US"


def test_fallback_rule():
    events = [_make_text_event("5561999999999", "mensagem qualquer")]
    actions = decide_responses(events)

    assert len(actions) == 1
    assert "Recebi sua mensagem" in actions[0]["text"]


def test_ignores_non_text_events():
    events = [{"from": "5561999999999", "type": "image", "id": "123"}]
    actions = decide_responses(events)

    # Não deve responder a eventos não-texto por padrão
    assert actions == []
