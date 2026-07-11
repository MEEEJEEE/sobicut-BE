from datetime import date, time

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


def get_week_of_month(d: date) -> int:
    """월 내 주차 (1~4). 29일 이후는 4주차로 합산."""
    return min((d.day - 1) // 7 + 1, 4)
