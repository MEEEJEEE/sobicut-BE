"""BPTI (Buying Pattern Type Indicator): 주력 구매 결정 심리특성 기반 소비 성격 유형"""
from sqlalchemy import extract, func
from sqlalchemy.orm import Session

from app.models import EmotionTag, Transaction, TransactionEmotion

BPTI_TYPES = {
    "스트레스": {"type": "FIRE", "label": "불지옥", "definition": "홧김 비용의 지배자",
             "message": "화가 날 때 지갑을 여는 타입! 스트레스 해소법을 돈 쓰기 말고 다른 걸로 찾아봐요."},
    "즉흥성": {"type": "FOG", "label": "안개 속", "definition": "충동이 이끄는 대로 사는 자",
            "message": "고민할 틈도 없이 결제 완료? 순간의 끌림이 지갑을 자주 여는 편이에요."},
    "비교회피": {"type": "LAZY", "label": "귀찮니즘", "definition": "비교보다 편리함을 택한 자",
             "message": "익숙한 걸 그냥 사는 편이군요. 가끔은 다른 선택지도 비교해봐요!"},
    "충분한숙고": {"type": "SAGE", "label": "신중한 현자", "definition": "따져보고 결정하는 자",
              "message": "비교하고 고민한 뒤에 결제하는 타입! 계획적인 소비 습관이 지갑을 지켜주고 있어요."},
    "장기적가치": {"type": "VISION", "label": "가치 투자자", "definition": "의미와 관계에 진심인 자",
              "message": "지금 당장보다 앞으로의 가치를 보고 쓰는 편이네요. 나와 주변을 위한 소비, 멋져요!"},
}

EMOTION_NAMES = list(BPTI_TYPES.keys())
NAME_BY_BPTI_TYPE = {v["type"]: name for name, v in BPTI_TYPES.items()}


def emotion_tag_counts(db: Session, user_id: int, year: int, month: int) -> dict[str, int]:
    """기간 내 지출 거래의 감정 태그별 횟수"""
    rows = (
        db.query(EmotionTag.name, func.count(TransactionEmotion.id))
        .join(TransactionEmotion, TransactionEmotion.emotion_tag_id == EmotionTag.id)
        .join(Transaction, Transaction.id == TransactionEmotion.transaction_id)
        .filter(
            Transaction.user_id == user_id,
            Transaction.type == "expense",
            extract("year", Transaction.transaction_date) == year,
            extract("month", Transaction.transaction_date) == month,
        )
        .group_by(EmotionTag.name)
        .all()
    )
    counts = {name: 0 for name in EMOTION_NAMES}
    counts.update(dict(rows))
    return counts


def emotion_radar(db: Session, user_id: int, year: int, month: int) -> dict[str, int]:
    """심리특성별 비율(%) — 5각형 레이더 그래프용. 태그 부착 횟수 기준 분포라
    5개 값의 합이 100%다 (한 거래에 여러 태그가 붙으면 그만큼 여러 태그에 나눠 집계)."""
    counts = emotion_tag_counts(db, user_id, year, month)
    total = sum(counts.values())
    if total == 0:
        return {name: 0 for name in EMOTION_NAMES}
    return {name: round(cnt / total * 100) for name, cnt in counts.items()}


def emotion_expense_ratio(txs: list[Transaction]) -> dict[str, int]:
    """태그별 '해당 태그가 붙은 지출 비율'(%) — 이번 달 전체 지출 거래 수 대비, 태그마다
    독립적으로 집계한다. emotion_radar와 달리 한 거래에 여러 태그가 붙을 수 있어
    5개 값의 합이 100%를 넘거나 안 될 수 있다 (중복 집계 막대 그래프용)."""
    if not txs:
        return {name: 0 for name in EMOTION_NAMES}
    counts = {name: 0 for name in EMOTION_NAMES}
    for tx in txs:
        for name in {t.name for t in tx.emotion_tags}:
            if name in counts:
                counts[name] += 1
    return {name: round(cnt / len(txs) * 100) for name, cnt in counts.items()}


def get_bpti(db: Session, user_id: int, year: int, month: int) -> dict | None:
    """주력 태그 기반 BPTI 유형. 태그 데이터 없으면 None."""
    counts = emotion_tag_counts(db, user_id, year, month)
    if sum(counts.values()) == 0:
        return None
    top = max(counts, key=counts.get)
    return BPTI_TYPES[top]
