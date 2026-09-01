"""히트맵 요일컷/시간대컷 알림 배치.

요일컷(이번 달 소비가 가장 많은 요일)과 시간대컷(이번 달 소비가 가장 많은
시간대)은 완전히 독립된 두 지표다. 예전엔 (요일,시간대) 조합 셀 하나만 골라서
요일이 화/수/목이면 시간대 라벨로 대체했는데("루틴 소비 컷"), 그 폴백을 없애고
둘 다 항상 각자 기준으로 따로 계산·발동한다. 구독 카테고리는 "히트맵알림"
하나로 통합 관리한다 (요일컷/시간대컷을 따로 켜고 끌 수는 없음).
"""
import logging
from datetime import date, datetime

from sqlalchemy import func
from sqlalchemy.orm import Session

from app.models import Notification, User
from app.services import report as report_service
from app.services.common import DAY_NAMES, get_time_slot
from app.services.web_push import notify_active_subscribers

logger = logging.getLogger(__name__)

PUSH_NOTIFICATION_TYPE = "히트맵알림"


def _already_sent_today(db: Session, user_id: int, notif_type: str, today: date) -> bool:
    return (
        db.query(Notification)
        .filter(
            Notification.user_id == user_id,
            Notification.type == notif_type,
            func.date(Notification.created_at) == today,
        )
        .first()
        is not None
    )


def process_heatmap_day_alerts(db: Session) -> int:
    """오늘이 이번 달 소비가 가장 많은 요일이면 알림 (매일 1회 체크)."""
    today = date.today()
    today_name = DAY_NAMES[today.weekday()]

    sent = 0
    users = db.query(User).filter(User.deleted_at.is_(None)).all()
    for user in users:
        report = report_service.heatmap_report(db, user.id, today.year, today.month)
        peak_day = report.get("peak_day")
        if not peak_day or peak_day["day"] != today_name:
            continue
        if _already_sent_today(db, user.id, "heatmap_day", today):
            continue

        title = peak_day["message"]  # 예: "목요일에 소비가 가장 많아요"
        message = f"이번 달 요일별 소비를 보면 {today_name}요일 지출이 가장 많았어요. 오늘은 조금 더 신경 써볼까요?"
        db.add(Notification(user_id=user.id, type="heatmap_day", title=title, message=message))
        notify_active_subscribers(db, user.id, PUSH_NOTIFICATION_TYPE, title, message, notification_type="heatmap_day")
        sent += 1

    db.commit()
    logger.info("히트맵 요일컷 알림 배치 완료: %d건 발송", sent)
    return sent


def process_heatmap_time_alerts(db: Session) -> int:
    """지금이 이번 달 소비가 가장 많은 시간대면 알림 (매일 06/11/14/19/23시 경계마다 체크)."""
    now = datetime.now()
    current_slot = get_time_slot(now.time())

    sent = 0
    users = db.query(User).filter(User.deleted_at.is_(None)).all()
    for user in users:
        report = report_service.heatmap_report(db, user.id, now.year, now.month)
        peak_slot = report.get("peak_time_slot")
        if not peak_slot or peak_slot["time_slot"] != current_slot:
            continue
        if _already_sent_today(db, user.id, "heatmap_time", now.date()):
            continue

        title = peak_slot["label"]  # 예: "야간 야망 컷"
        message = f"{current_slot} 시간대는 이번 달 소비가 가장 잦았던 때예요. 잠깐 멈춰볼까요?"
        db.add(Notification(user_id=user.id, type="heatmap_time", title=title, message=message))
        notify_active_subscribers(db, user.id, PUSH_NOTIFICATION_TYPE, title, message, notification_type="heatmap_time")
        sent += 1

    db.commit()
    logger.info("히트맵 시간대컷 알림 배치 완료: %d건 발송", sent)
    return sent
