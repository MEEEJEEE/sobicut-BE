"""Gemini API로 주간 소비 처방 3개를 생성하는 모듈.

외부 API 호출 규약은 `app/services/kakao_auth.py`와 동일하게 맞춘다:
모듈 상단 URL 상수, 전용 예외 클래스, httpx 동기 호출, try/except로
도메인 예외 변환(raise ... from e), 응답은 방어적으로 .get()으로 파싱.

kakao_auth는 timeout=5.0을 쓰지만 LLM 생성 응답은 수십 초가 걸리므로
여기서는 60.0을 쓴다.
"""
import json
import logging
import time
from datetime import date

import httpx

from app.core.config import settings

logger = logging.getLogger(__name__)

GEMINI_API_URL = "https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent"

# LLM 생성은 수 초~수십 초 걸린다. 5.0으로 낮추지 말 것.
REQUEST_TIMEOUT = 60.0

# 재시도: 네트워크 오류 / 5xx / JSON 파싱 실패만 대상. 4xx는 재시도하지 않는다.
MAX_ATTEMPTS = 3
BACKOFF_BASE_SECONDS = 1.0

# 낮추면 thinking 토큰 소모 후 응답이 잘려 JSON 파싱이 실패한다. 낮추지 말 것.
MAX_OUTPUT_TOKENS = 4096

# generate_prescription()이 summary(JSON 문자열)로 치환하는 자리표시 토큰.
SUMMARY_PLACEHOLDER = "{{WEEKLY_SUMMARY_JSON}}"

# TODO: 검증된 프롬프트로 교체. summary가 들어갈 자리에 SUMMARY_PLACEHOLDER
#       토큰({{WEEKLY_SUMMARY_JSON}})을 포함시키면 치환된다.
PRESCRIPTION_PROMPT_TEMPLATE = """(TODO: 검증된 프롬프트 붙여넣기 — {{WEEKLY_SUMMARY_JSON}} 포함)"""

# TODO: 검증된 responseSchema 붙여넣기 (Gemini generationConfig.responseSchema 형식)
PRESCRIPTION_RESPONSE_SCHEMA: dict = {}


class LLMPrescriptionError(Exception):
    """Gemini 처방 생성에 실패했거나 응답을 해석할 수 없는 경우."""


class _RetryableError(Exception):
    """재시도 대상 오류(네트워크 / 5xx / JSON 파싱 실패)를 나르는 내부용 예외."""


def _json_safe(value):
    """date 등 JSON 직렬화가 안 되는 값을 문자열로 변환한다."""
    if isinstance(value, dict):
        return {k: _json_safe(v) for k, v in value.items()}
    if isinstance(value, (list, tuple)):
        return [_json_safe(v) for v in value]
    if isinstance(value, date):  # datetime도 date의 서브클래스라 함께 처리됨
        return value.isoformat()
    return value


def _build_prompt(summary: dict) -> str:
    """build_weekly_summary() 반환 dict를 JSON 문자열로 만들어 프롬프트에 주입한다.

    summary 키 구조(app/services/weekly_summary.py 기준):
      period_start(date), period_end(date), total_spent(int), transaction_count(int),
      categories(list[{category, amount, ratio}]), avg_impulse_score(int|None),
      top_transactions(list[{merchant, amount, category, impulse_score}]),
      emotion_counts(dict[str, int])
    """
    summary_json = json.dumps(_json_safe(summary), ensure_ascii=False, indent=2)
    return PRESCRIPTION_PROMPT_TEMPLATE.replace(SUMMARY_PLACEHOLDER, summary_json)


def _concat_answer_parts(envelope: dict) -> str:
    """candidates[0].content.parts를 순회하며 thought 파트는 건너뛰고 text만 이어붙인다.

    thought 파트를 포함하면 JSON 파싱이 깨진다.
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


def _parse_prescriptions(parsed) -> list[dict]:
    """responseSchema 결과(리스트 또는 리스트를 감싼 dict)에서 처방 리스트를 꺼낸다."""
    if isinstance(parsed, dict):
        parsed = next((v for v in parsed.values() if isinstance(v, list)), None)
    if not isinstance(parsed, list) or not parsed:
        raise LLMPrescriptionError("Gemini 처방 응답 구조를 해석할 수 없습니다.")
    if not all(isinstance(item, dict) for item in parsed):
        raise LLMPrescriptionError("Gemini 처방 항목이 객체 형식이 아닙니다.")
    return parsed


def _request_prescription(request_body: dict) -> list[dict]:
    """Gemini에 1회 요청하고 처방 리스트를 반환한다.

    재시도 대상 오류는 _RetryableError로, 그 외(4xx·응답 구조 오류)는
    LLMPrescriptionError로 raise한다.
    """
    url = GEMINI_API_URL.format(model=settings.GEMINI_MODEL)
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
        raise _RetryableError(f"Gemini 서버 요청에 실패했습니다: {e}") from e

    if response.status_code >= 500:
        raise _RetryableError(f"Gemini 서버 오류 (status={response.status_code}).")
    if response.status_code != 200:
        raise LLMPrescriptionError(
            f"Gemini 요청이 거부되었습니다 (status={response.status_code}): {response.text[:200]}"
        )

    try:
        envelope = response.json()
    except json.JSONDecodeError as e:
        raise _RetryableError("Gemini 응답(envelope) JSON 파싱에 실패했습니다.") from e

    text = _concat_answer_parts(envelope)
    if not text:
        raise LLMPrescriptionError("Gemini 응답에 처방 텍스트가 없습니다.")

    try:
        parsed = json.loads(text)
    except json.JSONDecodeError as e:
        raise _RetryableError("Gemini 처방 본문 JSON 파싱에 실패했습니다.") from e

    return _parse_prescriptions(parsed)


def generate_prescription(summary: dict) -> list[dict]:
    """주간 소비 요약(build_weekly_summary 반환값)으로 소비 처방 리스트를 생성한다.

    네트워크 오류 / 5xx / JSON 파싱 실패는 지수 백오프로 최대 3회까지 재시도한다.
    최종 실패 시 LLMPrescriptionError를 raise한다 (None을 반환하지 않는다).
    """
    if not settings.GEMINI_API_KEY:
        raise LLMPrescriptionError("GEMINI_API_KEY가 설정되지 않았습니다.")

    request_body = {
        "contents": [{"parts": [{"text": _build_prompt(summary)}]}],
        "generationConfig": {
            "responseMimeType": "application/json",
            "responseSchema": PRESCRIPTION_RESPONSE_SCHEMA,
            "maxOutputTokens": MAX_OUTPUT_TOKENS,
        },
    }

    last_error: Exception | None = None
    for attempt in range(MAX_ATTEMPTS):
        try:
            return _request_prescription(request_body)
        except _RetryableError as e:
            last_error = e
            if attempt < MAX_ATTEMPTS - 1:
                sleep_seconds = BACKOFF_BASE_SECONDS * (2 ** attempt)
                logger.warning(
                    "Gemini 처방 생성 재시도 (%d/%d), %.1fs 후: %s",
                    attempt + 1, MAX_ATTEMPTS - 1, sleep_seconds, e,
                )
                time.sleep(sleep_seconds)

    raise LLMPrescriptionError("Gemini 처방 생성에 최종 실패했습니다.") from last_error
