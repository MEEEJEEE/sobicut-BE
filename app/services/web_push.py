"""웹 푸시 발송 로직 (VAPID 기반)."""
import json
import logging

from pywebpush import WebPushException, webpush
from sqlalchemy.orm import Session

from app.core.config import settings
from app.models import PushSubscription

logger = logging.getLogger(__name__)


def _vapid_claims() -> dict:
    return {"sub": f"mailto:{settings.VAPID_CLAIMS_EMAIL}"}


def send_push(subscription: PushSubscription, title: str, body: str) -> bool:
    """단일 구독 대상으로 웹 푸시 발송. 성공 여부를 bool로 반환하고 결과를 로깅한다."""
    subscription_info = {
        "endpoint": subscription.endpoint,
        "keys": {"p256dh": subscription.p256dh, "auth": subscription.auth},
    }
    try:
        webpush(
            subscription_info=subscription_info,
            data=json.dumps({"title": title, "body": body}),
            vapid_private_key=settings.VAPID_PRIVATE_KEY,
            vapid_claims=_vapid_claims(),
        )
        logger.info(
            "웹 푸시 발송 성공 user_id=%s notification_type=%s",
            subscription.user_id, subscription.notification_type,
        )
        return True
    except WebPushException as e:
        logger.warning(
            "웹 푸시 발송 실패 user_id=%s notification_type=%s reason=%s",
            subscription.user_id, subscription.notification_type, e,
        )
        return False


def send_test_notification(db: Session, user_id: int) -> bool:
    """user_id의 활성 구독 전체에 테스트 알림을 발송한다.

    구독이 하나도 없으면 False. 여러 구독 중 하나라도 성공하면 True.
    """
    subscriptions = (
        db.query(PushSubscription)
        .filter(PushSubscription.user_id == user_id, PushSubscription.is_active.is_(True))
        .all()
    )
    if not subscriptions:
        logger.warning("웹 푸시 테스트 발송 실패: user_id=%s에 활성 구독 없음", user_id)
        return False

    return any(
        send_push(sub, "소비컷 테스트 알림", "웹 푸시 알림이 정상적으로 연결되었습니다!")
        for sub in subscriptions
    )
