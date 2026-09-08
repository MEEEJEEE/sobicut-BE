"""주간 요약(build_weekly_summary 반환값)을 LLM 프롬프트에 넣을
"팩터 문장"으로 변환하는 모듈.

이 모듈은 LLM을 쓰지 않는다. 순수 파이썬 규칙으로만 문장을 만들며,
같은 입력이면 항상 같은 출력이 나온다(결정론적).

태그 분류는 아래 상수로 두되, 실제로 EMOTION_NAMES(app/services/bpti.py)에
존재하는 태그만 사용한다. 분류 목록에 있어도 EMOTION_NAMES에 없으면 무시하고,
EMOTION_NAMES에만 있고 분류에 없으면 역시 무시한다.
"""
from datetime import date

from app.services.bpti import EMOTION_NAMES

# 부정 태그 (프롬프트 문장에서 태그명을 그대로 노출)
NEGATIVE_TAGS = ("즉흥성", "스트레스", "비교회피")

# 긍정 태그 → 표시 문구. 태그명을 그대로 쓰지 않고 이 매핑을 쓴다.
POSITIVE_TAG_PHRASES = {
    "충분한숙고": "충분히 고민하고 결정한 소비 {n}회",
    "장기적가치": "오래 쓸 물건을 고른 소비 {n}회",
    "지속적만족": "오래 만족한 소비 {n}회",
}

_KNOWN_TAGS = set(EMOTION_NAMES)


def _has_final_consonant(word: str) -> bool:
    """한글 단어의 마지막 글자에 받침이 있는지: (ord(ch) - 0xAC00) % 28 != 0."""
    ch = word[-1]
    code = ord(ch) - 0xAC00
    if 0 <= code < 11172:
        return code % 28 != 0
    return False


def _subject_josa(word: str) -> str:
    """주격 조사: 받침 있으면 '이', 없으면 '가'."""
    return "이" if _has_final_consonant(word) else "가"


def _date_str(d) -> str | None:
    return d.isoformat() if isinstance(d, date) else d


def _score_delta(summary: dict, prev_summary: dict | None) -> int | None:
    """이번 주 - 지난주 충동 점수 차이. 계산 불가하면 None."""
    if prev_summary is None:
        return None
    cur = summary.get("avg_impulse_score")
    prev = prev_summary.get("avg_impulse_score")
    if cur is None or prev is None:
        return None
    return cur - prev


def _counts_desc(counts: dict, tags) -> list[tuple[str, int]]:
    """`tags` 중 EMOTION_NAMES에 있고 N>=1 인 것만, N 내림차순.

    동점이면 `tags`의 정의 순서를 유지한다(stable sort → 결정론적).
    """
    items = [
        (tag, counts[tag])
        for tag in tags
        if tag in _KNOWN_TAGS and counts.get(tag, 0) >= 1
    ]
    items.sort(key=lambda x: -x[1])
    return items


def _negative_factors(summary: dict, prev_summary: dict | None) -> list[str]:
    counts = summary.get("emotion_counts") or {}
    factors: list[str] = []

    # (규칙 3) 충동 점수 상승 문장 — 있으면 항상 최상위
    delta = _score_delta(summary, prev_summary)
    if delta is not None and delta >= 1:
        factors.append(f"충동 점수가 지난주보다 {delta}점 올랐어요")

    # (규칙 1) 부정 태그별 문장 — N 내림차순
    for tag, n in _counts_desc(counts, NEGATIVE_TAGS):
        factors.append(f"{tag}{_subject_josa(tag)} 달린 소비 {n}회")

    # (규칙 2) 1회 평균 결제액 — 태그 문장 다음
    tx_count = summary.get("transaction_count", 0)
    if tx_count >= 1:
        avg = round(summary.get("total_spent", 0) / tx_count)
        factors.append(f"1회 평균 {avg:,}원 결제")

    return factors[:3]


def _positive_factors(summary: dict, prev_summary: dict | None) -> list[str]:
    counts = summary.get("emotion_counts") or {}
    factors: list[str] = []

    # (규칙 2) 충동 점수 하락 문장 — 있으면 항상 최상위
    delta = _score_delta(summary, prev_summary)
    if delta is not None and delta <= -1:
        factors.append(f"충동 점수가 지난주보다 {-delta}점 내려갔어요")

    # (규칙 1) 긍정 태그별 문장 — 매핑 문구 사용, N 내림차순
    for tag, n in _counts_desc(counts, POSITIVE_TAG_PHRASES):
        factors.append(POSITIVE_TAG_PHRASES[tag].format(n=n))

    return factors[:2]


def _top_category(summary: dict) -> str | None:
    """categories 중 amount 최대 항목의 category. 전부 0이면 None."""
    best_category = None
    best_amount = 0
    for c in summary.get("categories") or []:
        amount = c.get("amount", 0)
        if amount > best_amount:
            best_amount = amount
            best_category = c.get("category")
    return best_category if best_amount > 0 else None


def build_factors(summary: dict, prev_summary: dict | None = None) -> dict:
    """주간 요약을 팩터 문장 묶음으로 변환한다.

    negative_factors / positive_factors 가 빈 리스트여도 정상 반환한다(예외 없음).
    """
    return {
        "period": {
            "week_start": _date_str(summary.get("period_start")),
            "week_end": _date_str(summary.get("period_end")),
        },
        "negative_factors": _negative_factors(summary, prev_summary),
        "positive_factors": _positive_factors(summary, prev_summary),
        "context": {
            "top_category": _top_category(summary),
            "impulse_score": summary.get("avg_impulse_score"),
            "prev_week_score": (
                prev_summary.get("avg_impulse_score") if prev_summary is not None else None
            ),
        },
    }
