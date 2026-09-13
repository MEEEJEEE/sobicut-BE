"""정규화된 가맹점명 하나를 Claude 로 소비 카테고리 분류하는 fallback.

이 함수는 POST /transactions/parse — 사용자가 응답을 기다리는 동기 경로 —
에서 호출된다. 응답 지연이 곧 UI 멈춤이므로 주간 처방 생성
(app/services/llm_prescription.py: timeout 60s / 재시도 3회)과 달리
timeout(settings.CLAUDE_CATEGORY_TIMEOUT, 기본 15s) / 재시도 0회 /
max_tokens 1024 로 짧게 잡는다.

재시도를 0회로 둔 이유: 실측상 이 경로의 지배적 실패 모드는 timeout 이고,
timeout 뒤 재시도가 성공하기까지 8.7초가 더 걸린다. timeout + 재시도 1회면
최악 30초를 사용자가 동기로 기다리게 되는데, 이 값은 룰·캐시 미스 후의 fallback
이라 실패해도 "미분류" 로 degrade 될 뿐이다. 대기 상한을 지키는 편이 낫다.

timeout 을 10s 에서 15s 로 올린 이유: structured outputs 는 스키마를 grammar 로
컴파일하며, 동일 스키마의 첫 요청에서 컴파일 지연이 붙는다. 컴파일 결과는 마지막
사용 시점부터 24시간 캐싱되므로 두 번째 요청부터는 영향이 없다. 배포 직후 첫 사용자가
컴파일 지연을 떠안지 않도록 워밍업 호출을 붙이는 것도 검토할 것.

_concat_answer_parts / _finish_reason 는 llm_prescription.py 와 중복이다.
동작 중인 처방 코드를 건드리지 않으려고 지금은 복사해 둔다.
추후 공용 Claude 클라이언트 모듈로 통합 검토.

프롬프트에는 정규화된 상호명만 전달한다. 금액·시간·사용자 정보는 절대 보내지 않는다.
어떤 실패(타임아웃·API 오류·레이트리밋(429)·과부하(529)·거절(refusal)·파싱 실패·
enum 밖 값·API 키 미설정)도 예외를 올리지 않고 None 을 반환한다. 각 경우는 로그로 남긴다.
"""
import json
import logging

import httpx

from app.core.categories import CATEGORIES
from app.core.config import settings

logger = logging.getLogger(__name__)

CLAUDE_API_URL = "https://api.anthropic.com/v1/messages"
ANTHROPIC_VERSION = "2023-06-01"

MAX_ATTEMPTS = 1  # 재시도 없음 — 근거는 모듈 docstring 참고
MAX_OUTPUT_TOKENS = 1024
TEMPERATURE = 0.0  # 분류기이므로 결정론적으로. 주의: Sonnet 5 / Opus 5 는
                   # temperature 를 기본값 외의 값으로 주면 400 을 반환한다.
                   # CLAUDE_MODEL_CATEGORY 를 그쪽으로 바꾸면 이 필드를 제거할 것.

# JSON Schema (소문자 타입 표기). Gemini 의 responseSchema 와 달리
# 모든 object 에 additionalProperties: false 가 필요하다.
CATEGORY_RESPONSE_SCHEMA: dict = {
    "type": "object",
    "properties": {
        "category": {"type": "string", "enum": list(CATEGORIES)},
    },
    "required": ["category"],
    "additionalProperties": False,
}

PROMPT = f"""너는 가맹점명을 소비 카테고리로 분류하는 분류기다.
아래 카테고리 중 정확히 하나를 고른다: {", ".join(CATEGORIES)}
- 입력은 가맹점명 한 개다. 다른 정보(금액·시간 등)는 주어지지 않는다.
- 어느 카테고리인지 애매하면 "모임/기타" 를 고른다.
- JSON 만 출력한다. 설명·인사말·마크다운 코드블록을 붙이지 않는다.

출력 형식:
{{"category": "..."}}"""


class _RetryableError(Exception):
    """네트워크 오류 / 5xx / 529 과부하 / JSON 파싱 실패 — 재시도 대상."""


def _concat_answer_parts(envelope: dict) -> str:
    """content 블록 배열을 순회하며 text 블록만 이어붙인다.

    Claude 응답의 content 는 블록 배열이고 thinking 블록이 섞여 올 수 있다.
    type == "text" 가 아닌 블록은 모두 건너뛴다.
    (llm_prescription.py 와 중복. 추후 통합 검토.)
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
    """stop_reason (예: "max_tokens", "refusal"). 없으면 None.

    (llm_prescription.py 와 중복. 추후 통합 검토.)
    """
    return envelope.get("stop_reason")


def _request_once(request_body: dict) -> str | None:
    """Claude 에 1회 요청하고 category 문자열을 반환한다.

    일시적 오류는 _RetryableError, 그 외(4xx·거절·빈 응답)는 None 을 반환한다.
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
            timeout=settings.CLAUDE_CATEGORY_TIMEOUT,
        )
    except httpx.HTTPError as e:
        raise _RetryableError(f"Claude 요청 실패: {e}") from e

    # 529(Overloaded)도 5xx 에 포함되어 재시도 대상으로 분류된다.
    if response.status_code >= 500:
        raise _RetryableError(f"Claude 서버 오류 (status={response.status_code}).")
    if response.status_code == 429:
        # 분당 요청 수 초과. Gemini 무료 티어의 일일 한도(RPD)와 달리 짧게 기다리면
        # 풀리는 값이지만, 이 경로는 동기 fallback 이라 대기하지 않고 즉시 포기한다.
        # 빈발하면 retry-after 헤더를 보고 상위 호출부에서 큐잉하는 방향을 검토할 것.
        logger.warning(
            "카테고리 LLM 레이트리밋 (429, retry-after=%s) — 미분류 처리: %s",
            response.headers.get("retry-after"),
            response.text[:200],
        )
        return None
    if response.status_code != 200:
        logger.warning(
            "카테고리 LLM 요청 거부 (status=%s): %s", response.status_code, response.text[:200]
        )
        return None

    try:
        envelope = response.json()
    except json.JSONDecodeError as e:
        raise _RetryableError("Claude 응답(envelope) JSON 파싱 실패.") from e

    # refusal 은 200 으로 내려오며 스키마를 따르지 않는다. 파싱 전에 걸러낸다.
    stop_reason = _finish_reason(envelope)
    if stop_reason == "refusal":
        logger.warning("카테고리 LLM 이 응답을 거부했습니다 (refusal) — 미분류 처리.")
        return None

    text = _concat_answer_parts(envelope)
    if not text:
        logger.warning(
            "카테고리 LLM 응답에 텍스트가 없습니다 (stop_reason=%s).", stop_reason
        )
        return None

    try:
        parsed = json.loads(text)
    except json.JSONDecodeError as e:
        # stop_reason == "max_tokens" 면 JSON 이 잘린 것이다. MAX_OUTPUT_TOKENS 를 확인할 것.
        raise _RetryableError(
            f"Claude 응답 본문 JSON 파싱 실패 (stop_reason={stop_reason})."
        ) from e

    if not isinstance(parsed, dict):
        logger.warning("카테고리 LLM 응답이 객체 형식이 아닙니다: %r", parsed)
        return None
    return parsed.get("category")


def classify_category(normalized_name: str) -> str | None:
    """정규화된 가맹점명 하나를 Claude 로 카테고리 분류한다. 실패 시 None."""
    if not settings.ANTHROPIC_API_KEY:
        logger.info("ANTHROPIC_API_KEY 미설정 — 카테고리 LLM fallback 건너뜀.")
        return None

    request_body = {
        "model": settings.CLAUDE_MODEL_CATEGORY,
        "max_tokens": MAX_OUTPUT_TOKENS,
        "temperature": TEMPERATURE,
        "system": PROMPT,
        "messages": [{"role": "user", "content": normalized_name}],
        "output_config": {
            "format": {
                "type": "json_schema",
                "schema": CATEGORY_RESPONSE_SCHEMA,
            }
        },
    }

    category: str | None = None
    for attempt in range(MAX_ATTEMPTS):
        try:
            category = _request_once(request_body)
            break
        except _RetryableError as e:
            if attempt < MAX_ATTEMPTS - 1:
                logger.warning("카테고리 LLM 재시도 (%d/%d): %s", attempt + 1, MAX_ATTEMPTS - 1, e)
                continue
            logger.warning("카테고리 LLM 일시적 오류 — 미분류 처리: %s", e)
            return None

    if category is None:
        return None
    if category not in CATEGORIES:
        logger.warning("카테고리 LLM 이 허용되지 않은 값 반환: %r", category)
        return None
    return category