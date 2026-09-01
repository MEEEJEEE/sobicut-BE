import logging

from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.triggers.cron import CronTrigger

from app.db.session import SessionLocal
from app.services.heatmap_batch import process_heatmap_day_alerts, process_heatmap_time_alerts
from app.services.level_batch import process_monthly_budget_bonus
from app.services.no_transaction_batch import process_no_transaction_reminders
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


def _run_heatmap_day_batch() -> None:
    db = SessionLocal()
    try:
        process_heatmap_day_alerts(db)
    except Exception:
        logger.exception("히트맵 요일컷 알림 배치 실행 중 오류")
    finally:
        db.close()


def _run_heatmap_time_batch() -> None:
    db = SessionLocal()
    try:
        process_heatmap_time_alerts(db)
    except Exception:
        logger.exception("히트맵 시간대컷 알림 배치 실행 중 오류")
    finally:
        db.close()


def _run_no_transaction_batch() -> None:
    db = SessionLocal()
    try:
        process_no_transaction_reminders(db)
    except Exception:
        logger.exception("가계부 기록 도우미 배치 실행 중 오류")
    finally:
        db.close()


def init_scheduler() -> None:
    """앱 시작 시 호출. 각 배치를 한국 시간(KST) 기준으로 실행한다."""
    _scheduler.add_job(
        _run_satisfaction_batch,
        CronTrigger(hour=21, minute=0, timezone="Asia/Seoul"),
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
    # 요일컷: 하루 시작 무렵 한 번만 체크 (오늘이 이번 달 최다 소비 요일인지)
    _scheduler.add_job(
        _run_heatmap_day_batch,
        CronTrigger(hour=9, minute=10, timezone="Asia/Seoul"),
        id="heatmap_day_alerts",
        name="Heatmap peak day alert batch",
        replace_existing=True,
    )
    # 시간대컷: 시간대 구분(아침 06/점심 11/저녁 14/밤 19/새벽 23) 경계마다 체크
    _scheduler.add_job(
        _run_heatmap_time_batch,
        CronTrigger(hour="6,11,14,19,23", minute=0, timezone="Asia/Seoul"),
        id="heatmap_time_alerts",
        name="Heatmap peak time-slot alert batch",
        replace_existing=True,
    )
    _scheduler.add_job(
        _run_no_transaction_batch,
        CronTrigger(hour=22, minute=0, timezone="Asia/Seoul"),
        id="no_transaction_reminders",
        name="No-transaction-today reminder batch",
        replace_existing=True,
    )
    if not _scheduler.running:
        _scheduler.start()


def shutdown_scheduler() -> None:
    if _scheduler.running:
        _scheduler.shutdown()
