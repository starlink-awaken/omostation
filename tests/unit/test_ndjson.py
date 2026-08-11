"""Contract tests for the backend-neutral incremental NDJSON decoder."""

from __future__ import annotations

import pytest


def test_ndjson_decodes_utf8_split_across_chunks_and_crlf() -> None:
    from omlxc.adapters.ndjson import NDJSONDecoder

    decoder = NDJSONDecoder()

    assert decoder.feed(b'{"text":"\xe4') == ()
    assert decoder.feed(b'\xbd\xa0\xe5\xa5\xbd"}\r') == ()
    assert decoder.feed(b'\n\n{"done":true}\n') == (
        {"text": "你好"},
        {"done": True},
    )
    assert decoder.finish() == ()


def test_ndjson_accepts_complete_final_object_without_newline() -> None:
    from omlxc.adapters.ndjson import NDJSONDecoder

    decoder = NDJSONDecoder()
    assert decoder.feed(b'{"done":true}') == ()
    assert decoder.finish() == ({"done": True},)


@pytest.mark.parametrize(
    "body",
    [b"not-json\n", b"[]\n", b'{"done":'],
)
def test_ndjson_rejects_non_object_or_truncated_records_without_echoing_input(
    body: bytes,
) -> None:
    from omlxc.adapters.ndjson import NDJSONDecodeError, NDJSONDecoder

    decoder = NDJSONDecoder()
    with pytest.raises(NDJSONDecodeError) as captured:
        decoder.feed(body)
        decoder.finish()

    rendered = f"{captured.value!s} {captured.value!r}"
    assert "not-json" not in rendered
    assert '{"done":' not in rendered


def test_ndjson_rejects_invalid_utf8_without_echoing_bytes() -> None:
    from omlxc.adapters.ndjson import NDJSONDecodeError, NDJSONDecoder

    decoder = NDJSONDecoder()
    with pytest.raises(NDJSONDecodeError) as captured:
        decoder.feed(b"\xff\n")

    assert "xff" not in f"{captured.value!s} {captured.value!r}".lower()
