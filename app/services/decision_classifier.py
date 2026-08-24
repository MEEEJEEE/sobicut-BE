"""자유 서술형 구매 결정 설명 → 5개 심리특성(BPTI 유형) 분류.

1단계(현재): 규칙/키워드 기반. 비용·지연 없이 즉시 응답하고, 기존 impulse_score
계산 방식(가중치 기반)과 결이 같다.
2단계(추후): 정확도가 부족하면 이 모듈의 `classify()` 시그니처(텍스트 in →
[{type, score}, ...] out)만 유지한 채 내부를 LLM 호출로 교체하면 된다.
"""
import re

_RULES: dict[str, dict[str, list[str]]] = {
    "FIRE": {
        "keywords": ["스트레스", "기분", "답답", "힘들", "우울", "화풀이", "해소", "짜증", "화나"],
        "patterns": [r"(스트레스|기분|답답|우울|짜증).*(샀|구매|썼|지름)", r"기분.*(풀|달래)"],
    },
    "FOG": {
        "keywords": ["그냥", "생각없이", "생각 없이", "충동", "우연히", "눈에 띄", "홧김", "무의식", "즉흥"],
        "patterns": [r"그냥.*샀", r"생각\s*없이.*샀", r"충동.*구매", r"눈에\s*띄.*샀"],
    },
    "LAZY": {
        "keywords": ["귀찮", "편해서", "편의", "항상", "늘 쓰던", "비교 안", "그냥 쓰던", "익숙"],
        "patterns": [r"귀찮.*(샀|써)", r"항상.*(써|쓰던)", r"비교.*안", r"다른\s*거\s*안\s*봄"],
    },
    "SAGE": {
        "keywords": ["비교", "리뷰", "검토", "신중", "고민", "며칠", "알아보", "따져", "가격 비교"],
        "patterns": [r"비교.*샀", r"(고민|검토).*(후|한\s*뒤|끝에)", r"리뷰.*보", r"며칠.*고민"],
    },
    "VISION": {
        "keywords": ["가치", "의미", "미래", "투자", "성장", "관계", "신념", "나눔", "가치관"],
        "patterns": [r"가치.*샀", r"미래.*투자", r"관계.*위해", r"가치관.*맞"],
    },
}

CODES = list(_RULES.keys())


def _score_text(text: str, rule: dict[str, list[str]]) -> float:
    score = 0.0
    for kw in rule["keywords"]:
        if kw in text:
            score += 1.0
    for pattern in rule["patterns"]:
        if re.search(pattern, text):
            score += 1.5  # 패턴 매칭은 단순 키워드 매칭보다 신뢰도 있게 가중
    return score


def classify(description: str) -> list[dict]:
    """(type, score) 후보를 score(0~1, 상대 비율) 내림차순으로 반환.

    키워드가 하나도 안 걸리면 전부 0점으로 반환 — 호출부가 confidence_level로
    "manual"(수동 선택) 처리하도록 유도한다.
    """
    text = (description or "").strip()
    raw_scores = {code: _score_text(text, rule) for code, rule in _RULES.items()}
    total = sum(raw_scores.values())

    if total == 0:
        return [{"type": code, "score": 0.0} for code in CODES]

    candidates = [{"type": code, "score": round(s / total, 3)} for code, s in raw_scores.items()]
    candidates.sort(key=lambda c: c["score"], reverse=True)
    return candidates


def confidence_level(top_score: float) -> str:
    """auto(자동 확정) | top3(상위 후보 제시) | manual(수동 선택 전체)"""
    if top_score >= 0.7:
        return "auto"
    if top_score >= 0.3:
        return "top3"
    return "manual"
