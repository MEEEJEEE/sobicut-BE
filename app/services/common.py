from datetime import date, time, timedelta

# 시간대 구분: 아침(06~11) 점심(11~14) 저녁(14~19) 밤(19~23) 새벽(23~06)
TIME_SLOTS = ["아침", "점심", "저녁", "밤", "새벽"]
DAY_NAMES = ["월", "화", "수", "목", "금", "토", "일"]


def get_time_slot(t: time) -> str:
    h = t.hour
    if 6 <= h < 11:
        return "아침"
    if 11 <= h < 14:
        return "점심"
    if 14 <= h < 19:
        return "저녁"
    if 19 <= h < 23:
        return "밤"
    return "새벽"


def get_iso_week_range(d: date) -> tuple[date, date]:
    """`d`가 속한 캘린더 주의 (월요일, 일요일)을 반환한다. `d.weekday()`는 월=0."""
    monday = d - timedelta(days=d.weekday())
    sunday = monday + timedelta(days=6)
    return monday, sunday


def get_week_of_month(d: date) -> int:
    """월 내 주차 (1~4), 월~일 기준.

    1주차 = 그 달 1일이 속한 월~일 주(1일이 월요일이 아니면 전달로 걸쳐도 1주차).
    5주차 이상은 4주차로 합산한다 — 예산은 week_1~4_budget 4칸만 있어서다.
    """
    first_monday, _ = get_iso_week_range(d.replace(day=1))
    return min((d - first_monday).days // 7 + 1, 4)
