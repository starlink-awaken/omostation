from mos.routing import backends_for_intent, classify_intent, rrf_fuse


def test_classify_intents():
    assert classify_intent("who calls function foo") == "code_structure"
    assert classify_intent("open tasks and debt") == "task_debt"
    assert classify_intent("my preference is vegetarian") == "preference_self"
    assert classify_intent("which ADR documents Memory OS") == "file_note"
    assert classify_intent("hello world") == "general"


def test_rrf_fuse_merges():
    a = [{"id": "x", "backend": "kos", "title": "x"}]
    b = [{"id": "x", "backend": "gbrain", "title": "x"}, {"id": "y", "backend": "gbrain"}]
    fused = rrf_fuse([a, b])
    assert fused[0]["id"] == "x"
    assert set(fused[0]["backends"]) >= {"kos", "gbrain"}


def test_backends_for_general():
    assert "kos" in backends_for_intent("general")
    assert "gbrain" in backends_for_intent("general")
