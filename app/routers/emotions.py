from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.core.deps import get_current_user
from app.db.session import get_db
from app.models import EmotionTag, User
from app.schemas.emotion import (
    DecisionCandidateOut,
    DecisionClassifyRequest,
    DecisionClassifyResponse,
    EmotionOut,
)
from app.services import decision_classifier
from app.services.bpti import NAME_BY_BPTI_TYPE

router = APIRouter(prefix="/emotions", tags=["Emotions"])


@router.get("", response_model=list[EmotionOut])
def list_emotions(user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    return db.query(EmotionTag).order_by(EmotionTag.id).all()


@router.post("/classify", response_model=DecisionClassifyResponse)
def classify_decision(
    body: DecisionClassifyRequest,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """구매 결정 설명을 5개 심리특성 후보로 분류 (미리보기 — 저장 안 함).

    top.score(신뢰도) 기준으로 프론트 UX를 나누면 된다:
    0.7 이상=자동 확정, 0.3~0.7=상위 후보 제시, 0.3 미만=전체 수동 선택.
    """
    tags_by_name = {t.name: t for t in db.query(EmotionTag).all()}
    ranked = decision_classifier.classify(body.description)

    candidates = [
        DecisionCandidateOut(
            emotion_tag_id=tags_by_name[NAME_BY_BPTI_TYPE[c["type"]]].id,
            name=NAME_BY_BPTI_TYPE[c["type"]],
            bpti_type=c["type"],
            score=c["score"],
        )
        for c in ranked
        if NAME_BY_BPTI_TYPE[c["type"]] in tags_by_name
    ]
    top = candidates[0]
    return DecisionClassifyResponse(
        confidence_level=decision_classifier.confidence_level(top.score),
        top=top,
        candidates=candidates,
    )
