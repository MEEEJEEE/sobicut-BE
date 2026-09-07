"""주간 LLM 소비 처방 사전 생성 배치 (매주 월요일 04:00 실행).

"막 끝난 지난주"를 대상으로 유저별 처방을 미리 생성해 llm_prescriptions에
저장해 둔다. (user_id, "weekly", 해당 주 월요일) 조합당 1건만 저장하며,
이미 있으면 건너뛴다(멱등).

기존 배치(no_transaction_batch 등)와 달리 개별 유저 루프 안에 try/except가
있다 — LLM은 실패가 잦은 외부 의존이라 한 유저 실패로 나머지 유저 처방까지
날아가면 안 되기 때문. web_push.send_push가 손상된 구독 하나로 배치 전체가
죽지 않게 방어하는 것과 같은 이유다. 단, LLMPrescriptionError만 잡는다 —
그 외 예외는 버그이므로 드러나야 한다.
"""
import logging
import time
from datetime import date, timedelta

from sqlalchemy.orm import Session

from app.core.config import settings
from app.models import LlmPrescription, User
from app.services.llm_prescription import LLMPrescriptionError, generate_prescription
from app.services.weekly_factors import build_factors
from app.services.weekly_summary import build_weekly_summary, get_iso_week_range

logger = logging.getLogger(__name__)

PERIOD_TYPE = "weekly"

# Gemini 무료 티어는 하루 20요청. 유저 사이 최소 간격을 둬 분당 요청수를 낮춘다.
REQUEST_INTERVAL_SECONDS = 2


def process_weekly_prescriptions(db: Session) -> int:
    """막 끝난 지난주 기준으로 유저별 주간 처방을 생성·저장한다. 저장 건수를 반환한다."""
    last_monday = get_iso_week_range(date.today())[0] - timedelta(days=7)
    prev_monday = last_monday - timedelta(days=7)

    saved = 0
    users = db.query(User).filter(User.deleted_at.is_(None)).all()
    for user in users:
        already = (
            db.query(LlmPrescription)
            .filter(
                LlmPrescription.user_id == user.id,
                LlmPrescription.period_type == PERIOD_TYPE,
                LlmPrescription.period_start == last_monday,
            )
            .first()
        )
        if already is not None:
            continue

        summary = build_weekly_summary(db, user, last_monday)
        if summary["transaction_count"] == 0:
            continue  # 거래 없는 주엔 처방이 의미 없다. LLM 호출 안 함 (쿼터 절약).

        prev_summary = build_weekly_summary(db, user, prev_monday)
        factors = build_factors(summary, prev_summary)
        if not factors["negative_factors"] and not factors["positive_factors"]:
            continue  # 뽑을 팩터가 없으면 LLM 호출 안 함.

        # 요청 간 최소 간격 (분당 요청수 제한 회피). 첫 유저에도 걸리지만 무시 가능한 지연.
        time.sleep(REQUEST_INTERVAL_SECONDS)
        try:
            prescriptions = generate_prescription(factors)
        except LLMPrescriptionError as e:
            logger.warning("주간 처방 생성 실패 user_id=%s: %s", user.id, e)
            continue

        db.add(
            LlmPrescription(
                user_id=user.id,
                period_type=PERIOD_TYPE,
                period_start=last_monday,
                content=prescriptions,
                model_name=settings.GEMINI_MODEL,
            )
        )
        saved += 1

    db.commit()
    logger.info("주간 LLM 처방 배치 완료: %d건 저장", saved)
    return saved
