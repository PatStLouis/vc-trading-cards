"""Session encode/decode tests."""
import pytest
from app.auth.session import encode_session, decode_session


def test_encode_decode_roundtrip():
    data = {"sub": "123", "username": "alice", "wallet_id": "w1"}
    token = encode_session(data)
    assert isinstance(token, str)
    assert "." in token
    decoded = decode_session(token)
    assert decoded == data


def test_decode_invalid_returns_none():
    assert decode_session("") is None
    assert decode_session("no-dot") is None
    assert decode_session("a.b.c") is None  # wrong number of parts
    assert decode_session("invalid.signature") is None  # bad signature


def test_decode_tampered_payload_returns_none():
    data = {"sub": "123"}
    token = encode_session(data)
    # Tamper: change first part (payload)
    parts = token.split(".")
    parts[0] = parts[0][:-1] + "x"
    assert decode_session(".".join(parts)) is None
