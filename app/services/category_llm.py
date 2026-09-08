"""정규화된 가맹점명 하나를 Gemini로 소비 카테고리 분류하는 fallback.

이 함수는 POST /transactions/parse — 사용자가 응답을 기다리는 동기 경로 —
에서 호출된다. 응답 지연이 곧 UI 멈춤이므로 주간 처방 생성
(app/services/llm_prescription.py: timeout 60s / 재시도 3회)과 달리
timeout 5s / 재시도 1회 / maxOutputTokens 1024 로 짧게 잡는다.

_concat_answer_parts / _finish_reason 는 llm_prescription.py 와 중복이다.
동작 중인 처방 코드를 건드리지 않으려고 지금은 복사해 둔다.
추후 공용 Gemini 클라이언트 모듈로 통합 검토.

프롬프트에는 정규화된 상호명만 전달한다. 금액·시간·사용자 정보는 절대 보내지 않는다.
어떤 실패(타임아웃·API 오류·재시도 소진·파싱 실패·enum 밖 값·API 키 미설정)도
예외를 올리지 않고 None 을 반환한다. 각 경우는 로그로 남긴다.
"""
import json
import logging

import httpx

from app.core.categories import CATEGORIES
from app.core.config import settings

logger = logging.getLogger(__name__)

GEMINI_API_URL = "https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent"

REQUEST_TIMEOUT = 5.0
MAX_ATTEMPTS = 2  # 최초 1회 + 재시도 1회
MAX_OUTPUT_TOKENS = 1024
TEMPERATURE = 0.0

CATEGORY_RESPONSE_SCHEMA: dict = {
    "type": "OBJECT",
    "properties": {
        "category": {"type": "STRING", "enum": list(CATEGORIES)},
    },
    "required": ["category"],
}

PROMPT = f"""너는 가맹점명을 소비 카테고리로 분류하는 분류기다.
아래 카테고리 중 정확히 하나를 고른다: {", ".join(CATEGORIES)}
- 입력은 가맹점명 한 개다. 다른 정보(금액·시간 등)는 주어지지 않는다.
- 어느 카테고리인지 애매하면 "모임/기타" 를 고른다.
- JSON 만 출력한다. 설명·인사말·마크다운 코드블록을 붙이지 않는다.

출력 형식:
{{"category": "..."}}"""


class _RetryableError(Exception):
    """네트워크 오류 / 5xx / JSON 파싱 실패 — 1회 재시도 대상."""


def _concat_answer_parts(envelope: dict) -> str:
    """candidates[0].content.parts 를 순회하며 thought 파트는 건너뛰고 text 만 이어붙인다.

    (llm_prescription.py 와 중복. 추후 통합 검토.)
    """
    candidates = envelope.get("candidates") or []
    if not candidates:
        return ""
    parts = (candidates[0].get("content") or {}).get("parts") or []
    chunks = []
    for part in parts:
        if part.get("thought") is True:
            continue
        text = part.get("text")
        if text:
            chunks.append(text)
    return "".join(chunks)


def _finish_reason(envelope: dict) -> str | None:
    """candidates[0].finishReason (예: "MAX_TOKENS", "SAFETY"). 없으면 None.

    (llm_prescription.py 와 중복. 추후 통합 검토.)
    """
    candidates = envelope.get("candidates") or []
    if not candidates:
        return None
    return candidates[0].get("finishReason")


def _request_once(url: str, request_body: dict) -> str | None:
    """Gemini 에 1회 요청하고 category 문자열을 반환한다.

    일시적 오류는 _RetryableError, 그 외(4xx·빈 응답)는 None 을 반환한다.
    """
    try:
        response = httpx.post(
            url,
            headers={
                "x-goog-api-key": settings.GEMINI_API_KEY,
                "Content-Type": "application/json",
            },
            json=request_body,
            timeout=REQUEST_TIMEOUT,
        )
    except httpx.HTTPError as e:
        raise _RetryableError(f"Gemini 요청 실패: {e}") from e

    if response.status_code >= 500:
        raise _RetryableError(f"Gemini 서버 오류 (status={response.status_code}).")
    if response.status_code != 200:
        logger.warning(
            "카테고리 LLM 요청 거부 (status=%s): %s", response.status_code, response.text[:200]
        )
        return None

    try:
        envelope = response.json()
    except json.JSONDecodeError as e:
        raise _RetryableError("Gemini 응답(envelope) JSON 파싱 실패.") from e

    text = _concat_answer_parts(envelope)
    if not text:
        logger.warning(
            "카테고리 LLM 응답에 텍스트가 없습니다 (finishReason=%s).", _finish_reason(envelope)
        )
        return None

    try:
        parsed = json.loads(text)
    except json.JSONDecodeError as e:
        raise _RetryableError("Gemini 응답 본문 JSON 파싱 실패.") from e

    if not isinstance(parsed, dict):
        logger.warning("카테고리 LLM 응답이 객체 형식이 아닙니다: %r", parsed)
        return None
    return parsed.get("category")


def classify_category(normalized_name: str) -> str | None:
    """정규화된 가맹점명 하나를 Gemini 로 카테고리 분류한다. 실패 시 None."""
    if not settings.GEMINI_API_KEY:
        logger.info("GEMINI_API_KEY 미설정 — 카테고리 LLM fallback 건너뜀.")
        return None

    request_body = {
        "systemInstruction": {"parts": [{"text": PROMPT}]},
        "contents": [{"role": "user", "parts": [{"text": normalized_name}]}],
        "generationConfig": {
            "responseMimeType": "application/json",
            "responseSchema": CATEGORY_RESPONSE_SCHEMA,
            "maxOutputTokens": MAX_OUTPUT_TOKENS,
            "temperature": TEMPERATURE,
        },
    }
    url = GEMINI_API_URL.format(model=settings.GEMINI_MODEL_CATEGORY)

    category: str | None = None
    for attempt in range(MAX_ATTEMPTS):
        try:
            category = _request_once(url, request_body)
            break
        except _RetryableError as e:
            if attempt < MAX_ATTEMPTS - 1:
                logger.warning("카테고리 LLM 재시도 (%d/%d): %s", attempt + 1, MAX_ATTEMPTS - 1, e)
                continue
            logger.warning("카테고리 LLM 재시도 소진: %s", e)
            return None

    if category is None:
        return None
    if category not in CATEGORIES:
        logger.warning("카테고리 LLM 이 허용되지 않은 값 반환: %r", category)
        return None
    return category
