from cockpit.web import mobile_api


def test_mobile_sign_never_marks_an_unexecuted_card_as_signed(monkeypatch):
    monkeypatch.setattr(mobile_api, "_ws", lambda: mobile_api.Path("/workspace"))
    monkeypatch.setattr(
        mobile_api,
        "_load_cards",
        lambda _ws: [{"message_id": "card-1", "payload": "safe content"}],
    )

    result = mobile_api.sign_card({"message_id": "card-1", "webauthn_assertion": "ok"})

    assert result == {
        "ok": False,
        "status": "awaiting_desktop_confirmation",
        "message_id": "card-1",
    }
