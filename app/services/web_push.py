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


def send_push(
    subscription: PushSubscription,
    title: str,
    body: str,
    *,
    notification_type: str,
    transaction_id: int | None = None,
) -> bool:
    """단일 구독 대상으로 웹 푸시 발송. 성공 여부를 bool로 반환하고 결과를 로깅한다.

    notification_type(예: "budget_monthly", "satisfaction_request")과
    transaction_id(해당 거래에 대한 알림일 때만)를 페이로드에 실어서, 프론트가
    URL을 직접 만들지 않고도 클릭 시 어느 화면으로 이동할지 이 값들로 판단할 수 있게 한다.
    """
    subscription_info = {
        "endpoint": subscription.endpoint,
        "keys": {"p256dh": subscription.p256dh, "auth": subscription.auth},
    }
    payload = {"title": title, "body": body, "type": notification_type}
    if transaction_id is not None:
        payload["transaction_id"] = transaction_id
    try:
        webpush(
            subscription_info=subscription_info,
            data=json.dumps(payload),
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
    except Exception:
        # 구독 정보(p256dh/auth)가 손상된 값이면 pywebpush가 WebPushException이 아니라
        # binascii.Error 등을 raise한다 — 이거 하나 때문에 배치 전체(다른 유저 발송분까지)가
        # 죽으면 안 되므로 여기서 넓게 잡는다.
        logger.exception(
            "웹 푸시 발송 중 예상 못한 오류 user_id=%s notification_type=%s",
            subscription.user_id, subscription.notification_type,
        )
        return False


def notify_active_subscribers(
    db: Session,
    user_id: int,
    subscription_category: str,
    title: str,
    body: str,
    *,
    notification_type: str,
    transaction_id: int | None = None,
) -> None:
    """subscription_category(히트맵알림 등 구독 카테고리)를 구독 중인 활성 구독 전체에 푸시를 발송한다.

    notification_type은 Notification.type(예: "budget_monthly")과 동일한 값을 넘겨서
    페이로드에 실어야 한다 — 구독 카테고리(4종)보다 세분화된, 프론트가 클릭 라우팅에 쓸 값.

    인앱 알림 생성 흐름(예: 거래 등록 직후 예산 초과 체크) 중간에 끼워 호출하므로,
    구독이 없거나 발송이 실패해도 예외를 올리지 않고 조용히 로깅만 한다.
    """
    subscriptions = (
        db.query(PushSubscription)
        .filter(
            PushSubscription.user_id == user_id,
            PushSubscription.notification_type == subscription_category,
            PushSubscription.is_active.is_(True),
        )
        .all()
    )
    for sub in subscriptions:
        send_push(sub, title, body, notification_type=notification_type, transaction_id=transaction_id)


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
        send_push(sub, "소비컷 테스트 알림", "웹 푸시 알림이 정상적으로 연결되었습니다!", notification_type="test")
        for sub in subscriptions
    )
