import logging

from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.triggers.cron import CronTrigger

from app.db.session import SessionLocal
from app.services.level_batch import process_monthly_budget_bonus
from app.services.satisfaction_batch import process_satisfaction_reminders

logger = logging.getLogger(__name__)

_scheduler = BackgroundScheduler()


def _run_satisfaction_batch() -> None:
    db = SessionLocal()
    try:
        process_satisfaction_reminders(db)
    except Exception:
        logger.exception("만족도 조사 알림 배치 실행 중 오류")
    finally:
        db.close()


def _run_monthly_budget_bonus_batch() -> None:
    db = SessionLocal()
    try:
        process_monthly_budget_bonus(db)
    except Exception:
        logger.exception("월간 예산 준수 보너스 배치 실행 중 오류")
    finally:
        db.close()


def init_scheduler() -> None:
    """앱 시작 시 호출. 매일 한국 시간 09:00에 배치들을 실행한다."""
    _scheduler.add_job(
        _run_satisfaction_batch,
        CronTrigger(hour=9, minute=0, timezone="Asia/Seoul"),
        id="satisfaction_reminders",
        name="Satisfaction reminder batch",
        replace_existing=True,
    )
    _scheduler.add_job(
        _run_monthly_budget_bonus_batch,
        CronTrigger(hour=9, minute=5, timezone="Asia/Seoul"),
        id="monthly_budget_bonus",
        name="Monthly budget compliance bonus batch",
        replace_existing=True,
    )
    if not _scheduler.running:
        _scheduler.start()


def shutdown_scheduler() -> None:
    if _scheduler.running:
        _scheduler.shutdown()
