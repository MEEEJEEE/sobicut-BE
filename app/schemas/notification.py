from datetime import datetime

from pydantic import BaseModel, ConfigDict


class NotificationOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    type: str
    title: str
    message: str
    is_read: bool
    transaction_id: int | None = None
    created_at: datetime


class PushSubscriptionKeys(BaseModel):
    p256dh: str
    auth: str


class PushSubscribeRequest(BaseModel):
    """브라우저의 PushSubscription.toJSON() 결과를 그대로 받는 형태."""

    endpoint: str
    keys: PushSubscriptionKeys
    notification_type: str


class PushUnsubscribeRequest(BaseModel):
    endpoint: str
    notification_type: str


class VapidPublicKeyResponse(BaseModel):
    public_key: str
