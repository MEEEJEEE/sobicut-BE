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
        # 삼성카드 승인 문자는 "삼성0000승인 ..."처럼 "카드" 없이 접두 4자리만 붙는
        # 형태가 있다. 정규식을 조이는 대신 리스트 맨 뒤에 두어, 다른 카드사 문자의
        # 가맹점명에 "삼성####"이 섞여도 그 카드사가 먼저 매칭되도록 한다.
        (re.compile(r"삼성(?=\d{4})"), "삼성카드"),
        # 우리카드도 "우리(0479)승인 ..."처럼 "카드" 없이 온다. "우리"만으로 매칭하면
        # "우리동네마트" 같은 상호를 오인식하므로 뒤따르는 문맥(이용안내 / 괄호+숫자)을
        # 조건으로 두고, 삼성 분기와 마찬가지로 리스트 맨 뒤에 둔다.
        (re.compile(r"우리(?:카드)?(?=\s*이용안내)|우리(?=\([\d*]{2,}\))"), "우리카드"),
    ]

    _CUMULATIVE_RE = re.compile(r"(누적|잔액)[:\s]*[\d,\-금액]*원?")
    _MONEY_RE = re.compile(r"([\d][\d,]{2,})\s*원")
    _ISO_DATE_RE = re.compile(r"(\d{4})-(\d{2})-(\d{2})")
    _SHORT_DATE_RE = re.compile(r"(\d{2})/(\d{2})")
    _TIME_RE = re.compile(r"([01]\d|2[0-3]):([0-5]\d)")
    # "홍*동" 처럼 마스킹된 이름: (1) "님"이 붙거나 (2) 뒤에 "(1234)" 코드가 오거나
    # (3) '*'를 포함한 채 공백/줄바꿈/문자열 끝 앞에 놓인 경우. (3)은 마스킹의
    # 특징인 '*' 포함을 필수로 요구해, 줄 끝의 실제 2~4자 상호명은 건드리지 않는다.
    _MASK_NAME_RE = re.compile(
        r"[가-힣*]{2,4}(?:님|(?=[\(（][\d*]{2,}[\)）]))"
        r"|(?=[가-힣]*\*)[가-힣*]{2,4}(?=\s|$)"
    )
    _MASK_CODE_RE = re.compile(r"[\d*]{2,}")
    _NOISE_WORDS_RE = re.compile(
        r"\[Web발신\]|\(Web발신\)|체크카드출금|체크\.?승인|승인시각|승인|일시불|"
        r"카드번호입력|자동결제|이용안내|금액|출금|계좌|고객명|시각|"
        # 문자 앞머리 장식 기호(줄 맨 앞의 •, ·, ▶ 등). 상호명 중간의 가운뎃점을
        # 지우지 않도록 줄머리에서만 제거한다.
        r"(?:^|(?<=\n))[ \t]*[•·∙‣▪◦▶►▸▷▹※]+"
    )
    # 노이즈·마스킹 토큰 제거 후 내용 없이 남는 괄호/대괄호 (안이 공백뿐인 경우 포함).
    _EMPTY_BRACKET_RE = re.compile(r"\(\s*\)|（\s*）|\[\s*\]|［\s*］")
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
        # 카드사명은 노이즈 제거보다 먼저 지운다. 삼성/우리 분기는 "승인"·"이용안내"
        # 같은 뒤따르는 문맥을 룩어헤드로 요구하는데, 노이즈 제거가 먼저 돌면 그
        # 문맥이 사라져 카드사명이 가맹점명에 잔류한다.
        for pattern, _name in self._COMPANY_PATTERNS:
            cleaned = pattern.sub(" ", cleaned)
        cleaned = self._NOISE_WORDS_RE.sub(" ", cleaned)
        # 빈 문자열로 치환한다. " "로 치우면 "롯데쇼핑(주)강남점"이 "롯데쇼핑 강남점"으로
        # 쪼개져 가맹점 사전 매칭(특히 prefix)이 실패한다. "(주)"는 항상 상호명 내부에만
        # 등장하므로 서로 다른 토큰이 붙을 위험이 없다.
        cleaned = self._COMPANY_SUFFIX_RE.sub("", cleaned)
        cleaned = self._MASK_NAME_RE.sub(" ", cleaned)
        cleaned = self._ISO_DATE_RE.sub(" ", cleaned)
        cleaned = self._SHORT_DATE_RE.sub(" ", cleaned)
        cleaned = self._TIME_RE.sub(" ", cleaned)
        cleaned = self._MONEY_RE.sub(" ", cleaned)
        cleaned = self._MASK_CODE_RE.sub(" ", cleaned)  # 마스킹된 카드번호/전화번호 등
        # 노이즈 제거 후 속이 빈 괄호만 지운다. "(CU)"처럼 실제 상호명 일부인
        # 괄호는 안이 채워져 있으므로 남긴다. 토큰이 빠지며 남은 "[ ]", "( )"도 정리한다.
        cleaned = self._EMPTY_BRACKET_RE.sub(" ", cleaned)
        # 구분자로 쓰인 구두점만 공백으로 바꾸고, 영숫자 사이의 "."은 남긴다.
        # ("SSG.COM" 같은 도메인/영문 상호가 "SSG COM"으로 갈라지는 것을 막는다.)
        cleaned = re.sub(
            r"(?<![A-Za-z0-9])[.:,\-]+|[.:,\-]+(?![A-Za-z0-9])", " ", cleaned
        )
        cleaned = re.sub(r"\s+", " ", cleaned).strip()
        cleaned = re.sub(r"\s*(사용|취소)$", "", cleaned).strip()

        # 가맹점 전체를 감싸는 바깥 괄호만 벗겨낸다 (예: "(씨유(CU) 자양한솔점)").
        if cleaned[:1] in "(（" and cleaned[-1:] in ")）":
            inner = cleaned[1:-1]
            if inner.count("(") + inner.count("（") == inner.count(")") + inner.count("）"):
                cleaned = inner.strip()

        return cleaned or None
