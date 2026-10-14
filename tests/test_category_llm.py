"""app.services.category_llm.classify_category 의 confidence 검증.

httpx.post 를 mock 해 실제 Claude 호출 없이 응답 본문만 바꿔가며 확인한다.
"""
import json
from unittest.mock import MagicMock

import pytest

from app.services import category_llm as cl


@pytest.fixture(autouse=True)
def _api_key(monkeypatch):
    # 키가 비어 있으면 classify_category 가 요청 전에 None 을 반환하므로 더미 값을 넣는다.
    monkeypatch.setattr(cl.settings, "ANTHROPIC_API_KEY", "test-key")


def _mock_claude_response(monkeypatch, payload: dict) -> MagicMock:
    """payload 를 text 블록 본문으로 담은 200 응답을 httpx.post 가 반환하도록 패치한다."""
    response = MagicMock(status_code=200)
    response.json.return_value = {
        "content": [{"type": "text", "text": json.dumps(payload, ensure_ascii=False)}],
        "stop_reason": "end_turn",
    }
    post = MagicMock(return_value=response)
    monkeypatch.setattr(cl.httpx, "post", post)
    return post


def test_high_confidence_valid_category_returns_category(monkeypatch):
    post = _mock_claude_response(monkeypatch, {"category": "식비", "confidence": 0.9})
    assert cl.classify_category("x") == "식비"
    post.assert_called_once()


def test_low_confidence_returns_none(monkeypatch):
    _mock_claude_response(monkeypatch, {"category": "식비", "confidence": 0.5})
    assert cl.classify_category("x") is None


def test_unclassifiable_returns_none(monkeypatch):
    _mock_claude_response(monkeypatch, {"category": cl.UNCLASSIFIABLE, "confidence": 0.9})
    assert cl.classify_category("x") is None


def test_missing_confidence_returns_none(monkeypatch):
    _mock_claude_response(monkeypatch, {"category": "식비"})
    assert cl.classify_category("x") is None


def test_out_of_range_confidence_returns_none(monkeypatch):
    _mock_claude_response(monkeypatch, {"category": "식비", "confidence": 1.5})
    assert cl.classify_category("x") is None


def test_bool_confidence_returns_none(monkeypatch):
    # bool 은 int 의 하위 타입이지만 확신도로 인정하지 않는다.
    _mock_claude_response(monkeypatch, {"category": "식비", "confidence": True})
    assert cl.classify_category("x") is None


def test_category_outside_categories_returns_none(monkeypatch):
    _mock_claude_response(monkeypatch, {"category": "없는값", "confidence": 0.9})
    assert cl.classify_category("x") is None
