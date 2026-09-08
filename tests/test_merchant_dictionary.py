"""app/data/merchant_dictionary.csv 로더(app.services.merchant_dictionary) 검증."""
import pytest

from app.core.categories import CATEGORIES
from app.services import merchant_dictionary as md
from app.services.category_matcher import guess_category

# CSV 데이터 행 수. app/data/merchant_dictionary.csv 헤더 제외.
_EXPECTED_ENTRY_COUNT = 345


def _all_entries() -> list[str]:
    entries: list[str] = []
    for keywords in md.PREFIX_RULES.values():
        entries += keywords
    for keywords in md.RULES.values():
        entries += keywords
    return entries


def test_total_entry_count():
    assert len(_all_entries()) == _EXPECTED_ENTRY_COUNT


def test_all_categories_are_subset_of_categories():
    cats = set(md.PREFIX_RULES) | set(md.RULES)
    assert cats <= set(CATEGORIES), cats - set(CATEGORIES)


def test_no_duplicate_merchant_names():
    entries = _all_entries()
    dupes = sorted({e for e in entries if entries.count(e) > 1})
    assert not dupes, dupes


def _write_csv(path, rows: list[str]) -> None:
    path.write_text(
        "merchant_name,category,match_type,note\n" + "\n".join(rows) + "\n",
        encoding="utf-8",
    )


def test_load_rejects_unknown_category(tmp_path):
    csv_path = tmp_path / "bad_category.csv"
    _write_csv(csv_path, ["스타벅스,없는카테고리,prefix,"])
    with pytest.raises(md.MerchantDictionaryError):
        md._load(csv_path)


def test_load_rejects_invalid_match_type(tmp_path):
    csv_path = tmp_path / "bad_match_type.csv"
    _write_csv(csv_path, ["스타벅스,식비,startswith,"])
    with pytest.raises(md.MerchantDictionaryError):
        md._load(csv_path)


def test_load_rejects_duplicate_merchant_name(tmp_path):
    csv_path = tmp_path / "dup_name.csv"
    _write_csv(csv_path, ["스타벅스,식비,prefix,", "스타벅스,생활,contains,중복"])
    with pytest.raises(md.MerchantDictionaryError):
        md._load(csv_path)


def test_load_rejects_empty_merchant_name(tmp_path):
    csv_path = tmp_path / "empty_name.csv"
    _write_csv(csv_path, [",식비,prefix,"])
    with pytest.raises(md.MerchantDictionaryError):
        md._load(csv_path)


def test_load_rejects_missing_file(tmp_path):
    with pytest.raises(md.MerchantDictionaryError):
        md._load(tmp_path / "does_not_exist.csv")


def test_length_ordering_prefers_more_specific_keyword():
    # "PC카페"/"스터디카페"(긴 키워드)가 "카페"(식비, 짧은 키워드)보다 먼저 매칭돼야 한다.
    assert guess_category("씨유역삼점") == "생활"
    assert guess_category("PC카페") == "문화/여가"
    assert guess_category("스터디카페") == "자기계발"


def test_category_decisions_from_csv():
    assert guess_category("넷플릭스") == "고정지출"
    assert guess_category("올리브영") == "쇼핑/패션"


def test_short_contains_keyword_does_not_swallow_unrelated_merchant():
    # "메가스터디"(자기계발, prefix)가 짧은 contains 키워드에 삼켜지지 않아야 한다.
    assert guess_category("메가스터디") == "자기계발"
