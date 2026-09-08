"""가맹점 사전 CSV 로더.

`app/data/merchant_dictionary.csv` 를 모듈 로드 시 1회 읽어 룰 매칭용 두 dict 를
구성한다. `category_matcher` 는 하드코딩 사전 대신 여기서 import 해 쓴다.

CSV 컬럼:
    merchant_name, category, match_type(prefix|contains), note

설계 원칙:
- CSV 경로는 이 모듈 파일 위치 기준으로 해석한다(작업 디렉토리에 의존하지 않는다).
- 표준 라이브러리 `csv` 만 쓴다. pandas 를 런타임 의존성에 추가하지 않는다.
- 로드 시 검증하고, 위반이면 앱 기동 시점에 실패한다(조용히 건너뛰지 않는다):
    (a) category 가 `app.core.categories.CATEGORIES` 에 없는 행
    (b) match_type 이 prefix/contains 가 아닌 행
    (c) merchant_name 중복
    (d) merchant_name 이 빈 값
- CSV 파일이 패키징/배포에서 누락되면 원인을 알 수 있는 명시적 에러를 낸다.
"""
from __future__ import annotations

import csv
from pathlib import Path

from app.core.categories import CATEGORIES

# app/services/merchant_dictionary.py -> app/data/merchant_dictionary.csv
_CSV_PATH = Path(__file__).resolve().parent.parent / "data" / "merchant_dictionary.csv"

_VALID_MATCH_TYPES = ("prefix", "contains")
_REQUIRED_COLUMNS = ("merchant_name", "category", "match_type")


class MerchantDictionaryError(RuntimeError):
    """가맹점 사전 CSV 가 없거나 형식이 잘못됐을 때 발생한다."""


def _load(csv_path: Path) -> tuple[dict[str, list[str]], dict[str, list[str]]]:
    """CSV 를 읽어 (PREFIX_RULES, RULES) 를 만든다. 위반이 있으면 예외를 던진다."""
    if not csv_path.is_file():
        raise MerchantDictionaryError(
            f"가맹점 사전 CSV 를 찾을 수 없습니다: {csv_path}\n"
            "패키징/배포에서 app/data/merchant_dictionary.csv 가 누락됐는지 확인하세요."
        )

    prefix_rules: dict[str, list[str]] = {}
    rules: dict[str, list[str]] = {}
    seen: set[str] = set()

    with csv_path.open(encoding="utf-8", newline="") as f:
        reader = csv.DictReader(f)
        missing = [c for c in _REQUIRED_COLUMNS if c not in (reader.fieldnames or [])]
        if missing:
            raise MerchantDictionaryError(
                f"가맹점 사전 CSV 헤더에 컬럼이 없습니다: {missing} ({csv_path})"
            )

        for row in reader:
            lineno = reader.line_num
            merchant_name = (row.get("merchant_name") or "").strip()
            category = (row.get("category") or "").strip()
            match_type = (row.get("match_type") or "").strip()

            if not merchant_name:
                raise MerchantDictionaryError(
                    f"{csv_path}:{lineno} merchant_name 이 빈 값입니다."
                )
            if match_type not in _VALID_MATCH_TYPES:
                raise MerchantDictionaryError(
                    f"{csv_path}:{lineno} match_type 이 prefix/contains 가 아닙니다: "
                    f"{match_type!r} (merchant_name={merchant_name!r})"
                )
            if category not in CATEGORIES:
                raise MerchantDictionaryError(
                    f"{csv_path}:{lineno} category 가 CATEGORIES 에 없습니다: "
                    f"{category!r} (merchant_name={merchant_name!r})"
                )
            if merchant_name in seen:
                raise MerchantDictionaryError(
                    f"{csv_path}:{lineno} merchant_name 이 중복됩니다: {merchant_name!r}"
                )
            seen.add(merchant_name)

            target = prefix_rules if match_type == "prefix" else rules
            target.setdefault(category, []).append(merchant_name)

    if not seen:
        raise MerchantDictionaryError(
            f"가맹점 사전 CSV 에 데이터 행이 없습니다: {csv_path}"
        )

    return prefix_rules, rules


#: match_type == "prefix" (startswith 매칭). category -> [merchant_name, ...]
#: match_type == "contains". category -> [merchant_name, ...]
PREFIX_RULES: dict[str, list[str]]
RULES: dict[str, list[str]]
PREFIX_RULES, RULES = _load(_CSV_PATH)
