"""Claude API로 주간 소비 처방 3개를 생성하는 모듈.

외부 API 호출 규약은 `app/services/kakao_auth.py`와 동일하게 맞춘다:
모듈 상단 URL 상수, 전용 예외 클래스, httpx 동기 호출, try/except로
도메인 예외 변환(raise ... from e), 응답은 방어적으로 .get()으로 파싱.

kakao_auth는 timeout=5.0을 쓰지만 LLM 생성 응답은 수십 초가 걸리므로
여기서는 60.0을 쓴다.

입력은 `app/services/weekly_factors.py`의 build_factors() 반환 dict다.
"""
import json
import logging
import time

import httpx

from app.core.config import settings

logger = logging.getLogger(__name__)

CLAUDE_API_URL = "https://api.anthropic.com/v1/messages"
ANTHROPIC_VERSION = "2023-06-01"

# LLM 생성은 수 초~수십 초 걸린다. 5.0으로 낮추지 말 것.
REQUEST_TIMEOUT = 60.0

# 재시도: 네트워크 오류 / 5xx / 529 과부하 / 429 레이트리밋 / JSON 파싱 실패가 대상.
# 그 외 4xx는 재시도하지 않는다.
# 429를 재시도 대상에 넣은 이유: Claude의 429는 분당 요청 수 제한이라 잠시 뒤 풀린다
# (Gemini 무료 티어의 일일 한도와 다르다). 이 경로는 배치 생성이라 대기해도 무방하다.
MAX_ATTEMPTS = 3
BACKOFF_BASE_SECONDS = 1.0

# 낮추면 thinking 토큰 소모 후 응답이 잘려 JSON 파싱이 실패한다. 낮추지 말 것.
MAX_OUTPUT_TOKENS = 4096

TEMPERATURE = 0.7  # 주의: Sonnet 5 / Opus 5 는 temperature를 기본값 외의 값으로 주면
                   # 400을 반환한다. CLAUDE_MODEL을 그쪽으로 바꾸면 이 필드를 제거할 것.

# 처방 개수 / 항목 최대 글자수 (프롬프트 문구와 검증 로직이 공유하는 값)
PRESCRIPTION_COUNT = 3
PRESCRIPTION_MAX_LEN = 20

# JSON Schema (소문자 타입 표기).
# Gemini의 responseSchema와 달리 (1) 모든 object에 additionalProperties: false가
# 필요하고 (2) minItems/maxItems는 지원되지 않는다. 개수 보장은 프롬프트 규칙 1번과
# _parse_prescriptions()의 검증으로 옮겼다.
PRESCRIPTION_RESPONSE_SCHEMA: dict = {
    "type": "object",
    "properties": {
        "prescription": {
            "type": "array",
            "items": {"type": "string"},
        }
    },
    "required": ["prescription"],
    "additionalProperties": False,
}

# system 파라미터로 넣는 고정 지시문. 9번 규칙은 원본에 없던 것을 추가한 것으로,
# build_factors()가 빈 negative_factors를 반환할 수 있어 대비한다.
PRESCRIPTION_PROMPT_TEMPLATE = f"""너는 20대 초중반 대학생의 소비 습관을 코칭하는 도우미다.
입력으로 이번 주 소비 분석 결과가 주어진다. 이를 바탕으로 처방전 {PRESCRIPTION_COUNT}개를 작성하라.

규칙:
1. 반드시 정확히 {PRESCRIPTION_COUNT}개를 작성한다. 더 많거나 적으면 안 된다.
2. 각 항목은 {PRESCRIPTION_MAX_LEN}자 이내로 쓴다. 공백 포함이다.
3. negative_factors의 위쪽 항목부터 순서대로 대응하는 행동을 제안한다.
4. 입력에 없는 숫자, 금액, 날짜, 카테고리를 만들어내지 않는다.
5. 이번 주 안에 바로 실행할 수 있는 구체적 행동으로 쓴다.
   "절약하기", "신중하게 생각하기" 같은 추상적 표현은 금지한다.
6. 존댓말을 쓰되 명령형 종결("~하기")로 짧게 끝낸다.
7. 비난하거나 죄책감을 주는 표현을 쓰지 않는다.
8. positive_factors는 이미 잘하고 있는 부분이므로 고치라고 하지 않는다.
9. negative_factors가 비어 있으면 positive_factors를 유지하는 행동을 제안한다.

출력 형식:
{{"prescription": ["...", "...", "..."]}}

JSON만 출력한다. 설명, 인사말, 마크다운 코드블록을 붙이지 않는다."""


class LLMPrescriptionError(Exception):
    """Claude 처방 생성에 실패했거나 응답을 해석할 수 없는 경우."""


class _RetryableError(Exception):
    """재시도 대상 오류(네트워크 / 5xx / 429 / JSON 파싱 실패)를 나르는 내부용 예외."""


def _concat_answer_parts(envelope: dict) -> str:
    """content 블록 배열을 순회하며 text 블록만 이어붙인다.

    Claude 응답의 content는 블록 배열이고 thinking 블록이 섞여 올 수 있다.
    thinking 블록을 포함하면 JSON 파싱이 깨지므로 type == "text"만 남긴다.
    """
    blocks = envelope.get("content") or []
    chunks = []
    for block in blocks:
        if block.get("type") != "text":
            continue
        text = block.get("text")
        if text:
            chunks.append(text)
    return "".join(chunks)


def _finish_reason(envelope: dict) -> str | None:
    """stop_reason (예: "max_tokens", "refusal"). 없으면 None."""
    return envelope.get("stop_reason")


def _parse_prescriptions(parsed) -> list[str]:
    """응답 본문이 {"prescription": [...]} 구조라는 전제로 문자열 리스트를 꺼낸다.

    구조가 어긋나면 _RetryableError (일시적 생성 오류로 보고 재시도).

    개수 검증을 여기서 하는 이유: Claude structured outputs는 minItems/maxItems를
    지원하지 않아 스키마가 개수를 보장하지 못한다. 글자수(PRESCRIPTION_MAX_LEN)는
    Gemini 시절에도 스키마가 아닌 프롬프트 규칙에만 의존했으므로 그대로 둔다.
    """
    if not isinstance(parsed, dict):
        raise _RetryableError("Claude 처방 응답이 객체 형식이 아닙니다.")
    prescription = parsed.get("prescription")
    if not isinstance(prescription, list):
        raise _RetryableError("Claude 응답에 prescription 리스트가 없습니다.")
    if not all(isinstance(item, str) for item in prescription):
        raise _RetryableError("Claude 처방 항목이 문자열이 아닙니다.")
    if len(prescription) != PRESCRIPTION_COUNT:
        raise _RetryableError(
            f"Claude 처방 개수가 {PRESCRIPTION_COUNT}개가 아닙니다 (실제 {len(prescription)}개)."
        )
    return prescription


def _request_prescription(request_body: dict) -> list[str]:
    """Claude에 1회 요청하고 처방 문자열 리스트를 반환한다.

    재시도 대상 오류는 _RetryableError로, 그 외(4xx·거절·빈 응답)는
    LLMPrescriptionError로 raise한다.
    """
    try:
        response = httpx.post(
            CLAUDE_API_URL,
            headers={
                "x-api-key": settings.ANTHROPIC_API_KEY,
                "anthropic-version": ANTHROPIC_VERSION,
                "content-type": "application/json",
            },
            json=request_body,
            timeout=REQUEST_TIMEOUT,
        )
    except httpx.HTTPError as e:
        raise _RetryableError(f"Claude 서버 요청에 실패했습니다: {e}") from e

    # 529(Overloaded)도 5xx에 포함되어 재시도 대상으로 분류된다.
    if response.status_code >= 500:
        raise _RetryableError(f"Claude 서버 오류 (status={response.status_code}).")
    if response.status_code == 429:
        raise _RetryableError(
            f"Claude 레이트리밋 (429, retry-after={response.headers.get('retry-after')})."
        )
    if response.status_code != 200:
        raise LLMPrescriptionError(
            f"Claude 요청이 거부되었습니다 (status={response.status_code}): {response.text[:200]}"
        )

    try:
        envelope = response.json()
    except json.JSONDecodeError as e:
        raise _RetryableError("Claude 응답(envelope) JSON 파싱에 실패했습니다.") from e

    # refusal은 200으로 내려오며 스키마를 따르지 않는다. 파싱 전에 걸러낸다.
    # 재시도해도 같은 결과이므로 즉시 LLMPrescriptionError로 올린다.
    stop_reason = _finish_reason(envelope)
    if stop_reason == "refusal":
        raise LLMPrescriptionError("Claude가 처방 생성을 거부했습니다 (refusal).")

    text = _concat_answer_parts(envelope)
    if not text:
        raise LLMPrescriptionError(
            f"Claude 응답에 처방 텍스트가 없습니다 (stop_reason={stop_reason})."
        )

    try:
        parsed = json.loads(text)
    except json.JSONDecodeError as e:
        # stop_reason == "max_tokens"면 JSON이 잘린 것이다. MAX_OUTPUT_TOKENS를 확인할 것.
        raise _RetryableError(
            f"Claude 처방 본문 JSON 파싱에 실패했습니다 (stop_reason={stop_reason})."
        ) from e

    return _parse_prescriptions(parsed)


def generate_prescription(factors: dict) -> list[str]:
    """주간 팩터(build_factors 반환값)로 소비 처방 문자열 리스트를 생성한다.

    네트워크 오류 / 5xx / 429 / JSON 파싱 실패는 지수 백오프로 최대 3회까지 재시도한다.
    최종 실패 시 LLMPrescriptionError를 raise한다 (None을 반환하지 않는다).
    """
    if not settings.ANTHROPIC_API_KEY:
        raise LLMPrescriptionError("ANTHROPIC_API_KEY가 설정되지 않았습니다.")

    user_prompt = "이번 주 분석 결과:\n" + json.dumps(factors, ensure_ascii=False, indent=2)
    request_body = {
        "model": settings.CLAUDE_MODEL,
        "max_tokens": MAX_OUTPUT_TOKENS,
        "temperature": TEMPERATURE,
        "system": PRESCRIPTION_PROMPT_TEMPLATE,
        "messages": [{"role": "user", "content": user_prompt}],
        "output_config": {
            "format": {
                "type": "json_schema",
                "schema": PRESCRIPTION_RESPONSE_SCHEMA,
            }
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
                    "Claude 처방 생성 재시도 (%d/%d), %.1fs 후: %s",
                    attempt + 1, MAX_ATTEMPTS - 1, sleep_seconds, e,
                )
                time.sleep(sleep_seconds)

    raise LLMPrescriptionError("Claude 처방 생성에 최종 실패했습니다.") from last_error