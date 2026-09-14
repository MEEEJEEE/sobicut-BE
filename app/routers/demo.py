"""발표/데모용 알림 배치 수동 트리거.

실제 운영 스케줄(APScheduler, app/core/scheduler.py)은 그대로 유지되고,
이 엔드포인트들은 그 스케줄을 기다리지 않고 즉시 한 번 실행시켜줄 뿐이다.
알림이 실제로 뜨는 조건(오늘이 이번 달 피크 요일/시간대인지, 오늘 거래 기록이
없는지, 만족도 조사 마감일이 오늘인지 등)은 그대로 적용되므로, 시연 전에
그 조건에 맞는 데이터를 미리 준비해둬야 한다 — 이 엔드포인트가 "무조건" 알림을
만들어주지는 않는다.

호출한 로그인 계정 본인에게만 적용되고(user_id로 스코프), force=true를 주면
"오늘 이미 보냈음" 같은 중복 방지 체크를 무시하고 다시 보낸다(리허설 중
반복 시연용). 스케줄러가 호출하는 운영 경로는 이 라우터를 거치지 않는다.
"""
from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.core.deps import get_current_user
from app.db.session import get_db
from app.models import User
from app.services.heatmap_batch import process_heatmap_day_alerts, process_heatmap_time_alerts
from app.services.level_batch import process_monthly_budget_bonus
from app.services.no_transaction_batch import process_no_transaction_reminders
from app.services.satisfaction_batch import process_satisfaction_reminders

router = APIRouter(prefix="/demo/trigger", tags=["Demo Triggers"])


@router.post("/heatmap-day")
def trigger_heatmap_day(
    force: bool = False,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    return {"sent": process_heatmap_day_alerts(db, user_id=user.id, force=force)}


@router.post("/heatmap-time")
def trigger_heatmap_time(
    force: bool = False,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    return {"sent": process_heatmap_time_alerts(db, user_id=user.id, force=force)}


@router.post("/no-transaction-reminder")
def trigger_no_transaction_reminder(
    force: bool = False,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    return {"sent": process_no_transaction_reminders(db, user_id=user.id, force=force)}


@router.post("/satisfaction-reminder")
def trigger_satisfaction_reminder(
    force: bool = False,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    return {"sent": process_satisfaction_reminders(db, user_id=user.id, force=force)}


@router.post("/budget-bonus")
def trigger_budget_bonus(
    force: bool = False,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    return {"granted": process_monthly_budget_bonus(db, user_id=user.id, force=force)}
