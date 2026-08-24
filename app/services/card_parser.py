"""카드 결제 문자 파서.

카드사마다 문구 순서·줄바꿈 구조가 제각각이라(신한: 한 줄 나열, KB/현대: 여러 줄
분리 등) 카드사별로 고정된 정규식 한 줄을 쓰는 방식은 실제 문자에서 쉽게 깨진다.
대신 문자에서 공통적으로 등장하는 요소(카드사명·금액·날짜·시간)를 각각 정규식으로
추출하고, 인식된 토큰을 모두 제거한 뒤 남는 텍스트를 가맹점명으로 판단한다.

패턴은 신한/삼성/현대/KB국민/NH농협(BC) 카드사의 실제 승인 문자 샘플
(kakao/credit-card-sms-parser 오픈소스 테스트 픽스처 기준)로 검증했고,
카카오뱅크/KB국민카드는 QA 과정에서 실제 문자로 추가 검증했다.
"""
import re
from datetime import date


class CardParseError(ValueError):
    """카드 문자에서 필요한 정보를 추출하지 못했을 때 발생."""


class CardParser:
    _COMPANY_PATTERNS: list[tuple[re.Pattern, str]] = [
        (re.compile(r"신한(?:카드)?"), "신한카드"),
        (re.compile(r"삼성(?:가족|법인)?카드"), "삼성카드"),
        (re.compile(r"현대카드"), "현대카드"),
        (re.compile(r"KB\s*국민(?:카드|체크)?|국민(?:카드|체크)"), "KB국민카드"),
        (re.compile(r"카카오\s*뱅크"), "카카오뱅크"),
        (re.compile(r"NH\s*농협(?:카드)?|농협(?:BC)?(?:카드)?"), "NH농협카드"),
    ]

    _CUMULATIVE_RE = re.compile(r"(누적|잔액)[:\s]*[\d,\-금액]*원?")
    _MONEY_RE = re.compile(r"([\d][\d,]{2,})\s*원")
    _ISO_DATE_RE = re.compile(r"(\d{4})-(\d{2})-(\d{2})")
    _SHORT_DATE_RE = re.compile(r"(\d{2})/(\d{2})")
    _TIME_RE = re.compile(r"([01]\d|2[0-3]):([0-5]\d)")
    _MASK_NAME_RE = re.compile(r"[가-힣*]{2,4}(?:님|(?=[\(（][\d*]{2,}[\)）]))")
    _MASK_CODE_RE = re.compile(r"[\d*]{2,}")
    _NOISE_WORDS_RE = re.compile(
        r"\[Web발신\]|\(Web발신\)|체크카드출금|체크\.승인|승인시각|승인|일시불|"
        r"출금|계좌|고객명|시각"
    )
    _COMPANY_SUFFIX_RE = re.compile(r"\(주\)|주식회사")

    def parse(self, message_text: str) -> dict:
        text = (message_text or "").strip()
        if not text:
            raise CardParseError("메시지가 비어 있습니다.")

        card_company = self._detect_company(text)
        if card_company is None:
            raise CardParseError("지원하지 않는 카드사이거나 인식할 수 없는 문자입니다.")

        amount = self._extract_amount(text)
        if amount is None:
            raise CardParseError("결제 금액을 찾을 수 없습니다.")

        transaction_date = self._extract_date(text)
        if transaction_date is None:
            raise CardParseError("거래 날짜를 찾을 수 없습니다.")

        transaction_time = self._extract_time(text)
        if transaction_time is None:
            raise CardParseError("거래 시간을 찾을 수 없습니다.")

        merchant = self._extract_merchant(text)
        if not merchant:
            raise CardParseError("가맹점명을 찾을 수 없습니다.")

        return {
            "amount": amount,
            "merchant": merchant,
            "transaction_date": transaction_date,
            "transaction_time": transaction_time,
            "card_company": card_company,
        }

    def _detect_company(self, text: str) -> str | None:
        for pattern, name in self._COMPANY_PATTERNS:
            if pattern.search(text):
                return name
        return None

    def _extract_amount(self, text: str) -> int | None:
        """누적/잔액 뒤에 붙는 금액은 제외하고, 실제 결제 금액을 찾는다."""
        cumulative_spans = [m.span() for m in self._CUMULATIVE_RE.finditer(text)]
        for m in self._MONEY_RE.finditer(text):
            if any(start <= m.start() < end for start, end in cumulative_spans):
                continue
            return int(m.group(1).replace(",", ""))
        return None

    def _extract_date(self, text: str) -> str | None:
        m = self._ISO_DATE_RE.search(text)
        if m:
            return f"{m.group(1)}-{m.group(2)}-{m.group(3)}"
        m = self._SHORT_DATE_RE.search(text)
        if m:
            # 카드사 문자는 연도를 생략하고 MM/DD만 주는 경우가 많아 현재 연도로 보정한다.
            year = date.today().year
            return f"{year:04d}-{m.group(1)}-{m.group(2)}"
        return None

    def _extract_time(self, text: str) -> str | None:
        m = self._TIME_RE.search(text)
        if m:
            return f"{m.group(1)}:{m.group(2)}"
        return None

    def _extract_merchant(self, text: str) -> str | None:
        # 대괄호로 가맹점을 감싸는 형식([혜화역 카페])을 우선 확인한다.
        # 단, 카드사명이나 "Web발신" 같은 헤더용 대괄호는 제외한다.
        for m in re.finditer(r"\[([^\[\]]+)\]", text):
            candidate = m.group(1).strip()
            if not candidate or candidate == "Web발신" or self._detect_company(candidate):
                continue
            return candidate

        # 대괄호 형식이 아니면, 인식된 토큰을 모두 제거하고 남는 텍스트를 가맹점으로 본다.
        cleaned = text
        cleaned = self._CUMULATIVE_RE.sub(" ", cleaned)
        cleaned = self._NOISE_WORDS_RE.sub(" ", cleaned)
        cleaned = self._COMPANY_SUFFIX_RE.sub(" ", cleaned)
        cleaned = self._MASK_NAME_RE.sub(" ", cleaned)
        for pattern, _name in self._COMPANY_PATTERNS:
            cleaned = pattern.sub(" ", cleaned)
        cleaned = self._ISO_DATE_RE.sub(" ", cleaned)
        cleaned = self._SHORT_DATE_RE.sub(" ", cleaned)
        cleaned = self._TIME_RE.sub(" ", cleaned)
        cleaned = self._MONEY_RE.sub(" ", cleaned)
        cleaned = self._MASK_CODE_RE.sub(" ", cleaned)  # 마스킹된 카드번호/전화번호 등
        # 노이즈 제거 후 속이 빈 괄호만 지운다. "(CU)"처럼 실제 상호명 일부인
        # 괄호는 안이 채워져 있으므로 남긴다.
        cleaned = re.sub(r"[\(（]\s*[\)）]|\[\s*\]", " ", cleaned)
        cleaned = re.sub(r"[.:,\-]+", " ", cleaned)
        cleaned = re.sub(r"\s+", " ", cleaned).strip()
        cleaned = re.sub(r"\s*(사용|취소)$", "", cleaned).strip()

        # 가맹점 전체를 감싸는 바깥 괄호만 벗겨낸다 (예: "(씨유(CU) 자양한솔점)").
        if cleaned[:1] in "(（" and cleaned[-1:] in ")）":
            inner = cleaned[1:-1]
            if inner.count("(") + inner.count("（") == inner.count(")") + inner.count("）"):
                cleaned = inner.strip()

        return cleaned or None
