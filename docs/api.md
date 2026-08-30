# API Specification (v2)

## 1. Overview
Emotion-based spending analysis API — 소비컷 (Consumer Cut)


---

## 2. Authentication

### POST /auth/signup
회원가입

Request:
```json
{
  "email": "test@test.com",
  "password": "1234",
  "nickname": "user1",
  "residence_type": "자취",
  "income_level": "30-60"
}
```

Response:
```json
{
  "id": 1,
  "email": "test@test.com"
}
```

---

### POST /auth/login
로그인

Request:
```json
{
  "email": "test@test.com",
  "password": "1234"
}
```

Response:
```json
{
  "access_token": "jwt-token"
}
```

---

### GET /auth/logout
로그아웃 (토큰 무효화)

Response:
```json
{
  "message": "로그아웃 완료"
}
```

---

### PATCH /auth/withdraw
회원탈퇴

Request:
```json
{
  "password": "1234"
}
```

Response:
```json
{
  "message": "탈퇴 완료"
}
```

---

### POST /auth/check-email
이메일(ID) 중복 확인

Request:
```json
{
  "email": "test@test.com"
}
```

Response:
```json
{
  "is_available": true
}
```

---

### POST /auth/validate-password
비밀번호 유효성 검사 (회원가입/정보수정 시 사용)

Request:
```json
{
  "password": "1234"
}
```

Response:
```json
{
  "is_valid": true,
  "message": "사용 가능한 비밀번호입니다."
}
```

---

## 3. Transactions

### POST /transactions/parse
카드 결제 문자 파싱 (지원 카드사: 신한/삼성/현대/KB국민/카카오뱅크/NH농협)

Request:
```json
{
  "message_text": "신한카드 승인되었습니다. [혜화역 카페] 5,500원 2026-08-22 14:32"
}
```

Response:
```json
{
  "amount": 5500,
  "merchant": "혜화역 카페",
  "transaction_date": "2026-08-22",
  "transaction_time": "14:32",
  "card_company": "신한카드"
}
```

> 파싱 결과는 거래 등록(`POST /transactions`)을 대신하지 않는다. 프론트에서 파싱 결과를
> 폼에 채운 뒤 사용자가 확인/수정 후 별도로 `POST /transactions`를 호출해야 한다.
> 지원하지 않는 카드사이거나 필수 항목(금액/날짜/시간/가맹점)을 추출하지 못하면 `422`를 반환한다.

---

### POST /transactions
지출/수입 등록

Request:
```json
{
  "amount": 10000,
  "type": "expense",
  "category": "식비",
  "merchant": "스타벅스",
  "description": "커피",
  "transaction_date": "2026-04-19",
  "transaction_time": "14:30"
}
```

Response:
```json
{
  "id": 1
}
```

---

### GET /transactions
전체 거래 내역 조회

Query Parameters:
- `year` (int, optional)
- `month` (int, optional)
- `week` (int, optional): ISO week number
- `date` (string, optional): `YYYY-MM-DD` 단건 조회 (다른 필터와 함께 사용 가능)
- `type` (string, optional): `income` | `expense`
- `category` (string, optional)

Response:
```json
[
  {
    "id": 1,
    "amount": 10000,
    "type": "expense",
    "category": "식비",
    "merchant": "스타벅스",
    "description": "커피",
    "transaction_date": "2026-04-19",
    "transaction_time": "14:30",
    "emotion_tags": [
      { "id": 1, "name": "스트레스" }
    ],
    "created_at": "2026-04-19T14:30:00"
  }
]
```

---

### GET /transactions/{id}
단건 거래 상세 조회

Response:
```json
{
  "id": 1,
  "amount": 10000,
  "type": "expense",
  "category": "식비",
  "merchant": "스타벅스",
  "description": "커피",
  "transaction_date": "2026-04-19",
  "transaction_time": "14:30",
  "emotion_tags": [
    { "id": 1, "name": "스트레스" }
  ],
  "impulse_score": 72,
  "created_at": "2026-04-19T14:30:00"
}
```

---

### PUT /transactions/{id}
거래 수정

---

### DELETE /transactions/{id}
거래 삭제

---

## 4. Emotion (구매 결정 심리특성)

> v3: 감정 태그 6종 → 구매 결정 심리특성 5종(스트레스/즉흥성/비교회피/충분한숙고/장기적가치)으로
> 명칭 변경. 프론트는 "계획 여부"(즉흥성/충분한숙고 중 1개) + "소비 특성"(스트레스/비교회피/
> 장기적가치 중 최대 3개) 칩을 클릭해서 고른 태그 ID를 그대로 보낸다 — 자유 텍스트 입력이나
> 서버 쪽 자동 분류는 없다. 거래 1건당 최대 4개, 중복 불가.

### GET /emotions
심리특성 목록 전체 조회

Response:
```json
[
  { "id": 1, "name": "스트레스",   "type": "negative" },
  { "id": 2, "name": "즉흥성",     "type": "negative" },
  { "id": 3, "name": "비교회피",   "type": "negative" },
  { "id": 4, "name": "충분한숙고", "type": "positive" },
  { "id": 5, "name": "장기적가치", "type": "positive" }
]
```

---

### POST /transactions/{id}/emotions
거래에 심리특성 태그 등록 (1~4개, 중복 불가). 호출할 때마다 "현재 선택 상태 전체"로
간주해서, 이전에 있었지만 이번 요청에 없는 태그는 삭제되고 새로 온 태그만 추가된다
(부분 추가가 아니라 교체).

Request:
```json
{
  "emotion_tag_ids": [2, 1, 3]
}
```

> 예: "아니요, 바로 샀어요"(즉흥성=2) + "스트레스 받아서"(스트레스=1) + "비교 안 하고"(비교회피=3)

Response:
```json
{
  "message": "감정 태그 등록 완료"
}
```

에러:
- 5개 이상 또는 0개 선택, 중복 ID 포함 → `422`
- 존재하지 않는 태그 ID 포함 → `404`

---

## 5. Budget

### GET /budget
예산 조회

Response:
```json
{
  "monthly_budget": 1000000,
  "weekly_budget": 250000,
  "weekly_budgets": {
    "week_1": 250000,
    "week_2": 250000,
    "week_3": 250000,
    "week_4": 250000
  }
}
```

> `weekly_budgets`: 월별 주차별로 분할된 예산. 주차별 개별 관리가 필요한 리포트 화면에서 활용.

---

### PUT /budget
예산 수정

Request:
```json
{
  "monthly_budget": 1000000,
  "weekly_budget": 250000,
  "weekly_budgets": {
    "week_1": 250000,
    "week_2": 250000,
    "week_3": 250000,
    "week_4": 250000
  }
}
```

---

## 6. Satisfaction

### POST /satisfactions
만족도 등록 (5만원 이상 고가 소비, 1일/7일/30일 후 3회 입력)

Request:
```json
{
  "transaction_id": 1,
  "day_type": "7일",
  "score": 3
}
```

> `day_type`: `"1일"` | `"7일"` | `"30일"` — 후회도(regret_score) 계산 시
> `q = 0.2*q_1일 + 0.3*q_7일 + 0.5*q_30일` 가중 평균에 쓰인다.
> `score`: 1(매우 후회) ~ 5(매우 만족)

Response:
```json
{
  "id": 1,
  "transaction_id": 1,
  "day_type": "7일",
  "message": "만족도 등록 완료"
}
```

---

### GET /satisfactions?year=&month=
지정 월(생략 시 이번 달)에 **제출된**(`submitted_at` 기준) 만족도를 거래 단위로
묶어서 일괄 조회. 결과 페이지에서 거래마다 `GET /transactions/{id}/satisfactions`를
반복 호출하지 않도록 만든 목록 API. 거래일(`transaction_date`) 기준이 아니라
"이번 달에 받은 응답" 기준이라, 지난달에 산 물건의 30일차 응답이 이번 달에 들어왔으면
이번 달 목록에 잡힌다.

Query Parameters:
- `year` (int, optional)
- `month` (int, optional)

Response:
```json
[
  {
    "transaction_id": 5,
    "merchant": "무신사",
    "amount": 89000,
    "transaction_date": "2026-06-01",
    "satisfactions": [
      { "day_type": "7일", "score": 5, "submitted_at": "2026-08-26T10:00:00" },
      { "day_type": "30일", "score": 3, "submitted_at": "2026-08-31T09:00:00" }
    ]
  }
]
```

> `transaction_date` 최신순 정렬. 각 거래의 `satisfactions`는 day_type 순서(1일→7일→30일).

---

### GET /satisfactions/pending
만족도 미입력 건 조회 (팝업 트리거용)

Response:
```json
[
  {
    "transaction_id": 5,
    "merchant": "무신사",
    "amount": 89000,
    "day_type": "7일",
    "due_date": "2026-04-26"
  }
]
```

---

### GET /transactions/{id}/satisfactions
거래 하나에 대해 시점별(1일/7일/30일)로 제출된 만족도 결과 비교 조회
(결과 페이지에서 "7일 후 5점 → 30일 후 3점" 같은 비교 표시용).
`transaction_id`만으로는 어느 시점 응답인지 구분이 안 돼서, 이 엔드포인트가
해당 거래의 제출 완료된 기록만 day_type 순서(1일→7일→30일)로 반환한다.

Response:
```json
[
  { "day_type": "7일", "score": 5, "submitted_at": "2026-04-26T10:00:00" },
  { "day_type": "30일", "score": 3, "submitted_at": "2026-05-19T10:00:00" }
]
```

---

## 7. Notifications

### GET /notifications
알림 목록 조회

Query Parameters:
- `type` (string, optional): 알림 종류 필터
  - `budget_weekly`: 주간 예산 초과 ✅ 구현됨 (거래 등록 시 체크, 소비컷알림 구독자에게 웹 푸시도 함께 발송)
  - `budget_monthly`: 월간 예산 초과 ✅ 구현됨 (위와 동일)
  - `impulse_warning`: 충동 소비 경고 ✅ 구현됨 (위와 동일)
  - `heatmap_time`: 시간대 소비 패턴 경고 ⛔️ 미구현 (트리거 조건 미정)
  - `heatmap_day`: 요일 소비 패턴 경고 ⛔️ 미구현 (트리거 조건 미정)
  - `satisfaction_request`: 만족도 입력 요청 ✅ 구현됨 — 고가 소비(5만원 이상) 후
    정확히 7일/30일째 되는 날 매일 09:00(KST) 배치로 인앱 알림 + 만족도조사알림
    구독자에게 웹 푸시 발송. `satisfaction_notification_logs` 테이블로 중복 발송 방지.
    (참고: `GET /satisfactions/pending`은 이 배치와 별개로, 마감일이 지났고 아직
    미제출인 건을 그때그때 계산해서 보여주는 용도라 배치 발송 여부와 무관하게 계속 조회 가능)

Response:
```json
[
  {
    "id": 1,
    "type": "budget_weekly",
    "title": "주간 예산 초과",
    "message": "이번 주 예산을 초과했습니다.",
    "is_read": false,
    "created_at": "2026-04-19T14:30:00"
  },
  {
    "id": 2,
    "type": "heatmap_time",
    "title": "야간 야망 컷 ✂️",
    "message": "밤 11시, 지금이 가장 많이 쓰는 시간대예요!",
    "is_read": false,
    "created_at": "2026-04-19T23:05:00"
  }
]
```

---

### PUT /notifications/{id}
알림 읽음 처리

Response:
```json
{
  "message": "읽음 처리 완료"
}
```

---

### PUT /notifications/read-all
전체 알림 읽음 처리

Response:
```json
{
  "message": "전체 읽음 처리 완료"
}
```

---

### GET /notifications/vapid-public-key
웹 푸시 구독 생성 시 프론트에서 `pushManager.subscribe()`의 `applicationServerKey`로
사용할 VAPID 공개키. 인증 불필요.

Response:
```json
{
  "public_key": "BP2hSYWVxa09LkZ4NhzkbSM1w23dB00ThxWZ4nbsoHvgwGO..."
}
```

---

### POST /notifications/subscribe
웹 푸시 구독 등록. 브라우저 `PushSubscription.toJSON()` 결과를 그대로 전달하면 된다.
같은 `endpoint`+`notification_type` 조합으로 다시 호출하면 기존 구독을 갱신한다
(재구독 시 `is_active`도 다시 활성화).

Request:
```json
{
  "endpoint": "https://fcm.googleapis.com/fcm/send/xxxxx",
  "keys": {
    "p256dh": "...",
    "auth": "..."
  },
  "notification_type": "소비컷알림"
}
```

> `notification_type`: `"소비컷알림"` | `"만족도조사알림"`

Response:
```json
{
  "message": "구독 등록 완료"
}
```

---

### POST /notifications/unsubscribe
특정 `notification_type` 구독만 해제 (같은 endpoint의 다른 타입 구독은 유지).

Request:
```json
{
  "endpoint": "https://fcm.googleapis.com/fcm/send/xxxxx",
  "notification_type": "소비컷알림"
}
```

Response:
```json
{
  "message": "구독 해제 완료"
}
```

---

### POST /notifications/test-push
로그인한 사용자의 활성 구독 전체로 테스트 알림을 발송한다.
활성 구독이 없으면 `404`, 구독은 있으나 발송(브라우저 푸시 서비스 응답)에
실패하면 `502`를 반환한다.

Response:
```json
{
  "message": "테스트 알림을 발송했습니다."
}
```

---

## 8. My Page

### GET /users/me
내 프로필 조회

Response:
```json
{
  "id": 1,
  "email": "test@test.com",
  "nickname": "user1",
  "residence_type": "자취",
  "income_level": "30-60",
  "created_at": "2026-01-01T00:00:00"
}
```

---

### GET /users/me/level
내 정령 레벨 조회 (게이미피케이션)

Response:
```json
{
  "level": 2,
  "level_name": "박스 몬스터",
  "current_exp": 56,
  "next_level_exp": 90,
  "description": "지갑의 뼈대가 잡히고 있어요! 소비 습관이 조금씩 성장하고 있어요."
}
```

---

### GET /users/me/settings
내 정보 수정 페이지 초기 데이터 조회

Response:
```json
{
  "email": "test@test.com",
  "nickname": "user1",
  "residence_type": "자취",
  "income_level": "30-60"
}
```

---

### PATCH /users/me/nickname
닉네임 수정

Request:
```json
{
  "nickname": "newNickname"
}
```

---

### PATCH /users/me/password
비밀번호 수정

Request:
```json
{
  "current_password": "1234",
  "new_password": "5678"
}
```

---

### PATCH /users/me/residence-type
거주 형태 수정

Request:
```json
{
  "residence_type": "기숙사"
}
```

---

### PATCH /users/me/income-level
소득 구간 수정

Request:
```json
{
  "income_level": "60-100"
}
```

---

## 9. Reports — 충동 지수 / 지갑 온도 / BPTI

### GET /reports/scores
메인 페이지 및 내 소비 페이지 요약 지표 조회
(충동 지수 + 지갑 온도 + BPTI 유형 한 번에 반환)

Response:
```json
{
  "impulse_score": 72,
  "wallet_temperature": {
    "my_temp": 72,
    "peer_avg_temp": 65,
    "diff": 7,
    "level": "보통",
    "emoji": "😐",
    "message": "지갑이 적당히 데워지고 있어요. 이 흐름을 유지해보세요"
  },
  "bpti": {
    "type": "FIRE",
    "label": "불지옥",
    "definition": "홧김 비용의 지배자",
    "message": "화가 날 때 지갑을 여는 타입! 스트레스 해소법을 돈 쓰기 말고 다른 걸로 찾아봐요."
  }
}
```

---

### GET /reports/impulse
충동 지수 상세 조회
(소비 상세 리포트 페이지 / 충동 상세 리포트 페이지)

Query Parameters:
- `year` (int)
- `month` (int)

Response:
```json
{
  "impulse_score": 72,
  "threshold": 75,
  "is_warning": false,
  "breakdown": {
    "time_abnormal": 0.5,
    "amount_burden": 0.8,
    "repeat_consumption": 0.5,
    "peer_comparison": 0.6,
    "regret_score": 0.7
  },
  "emotion_breakdown": {
    "스트레스": 0.4,
    "즉흥성": 0.2,
    "비교회피": 0.1,
    "충분한숙고": 0.2,
    "장기적가치": 0.1
  },
  "top_impulse_transactions": [
    {
      "id": 3,
      "merchant": "쿠팡",
      "amount": 45000,
      "transaction_date": "2026-04-15",
      "impulse_score": 88
    }
  ],
  "peer_avg_impulse_score": 58,
  "week_over_week": {
    "this_week": 65,
    "last_week": 58,
    "diff": 7
  }
}
```

> `peer_avg_impulse_score`: 같은 그룹(거주형태+소득구간) 사용자들의 이번 달 평균 충동 점수.
> 비교 대상 또래가 없으면 `null`.
> `week_over_week`: 오늘 기준 최근 7일 vs 그 이전 7일의 평균 충동 점수. 해당 기간에
> 지출 거래가 없으면 `this_week`/`last_week`가 `null`이고, 둘 중 하나라도 `null`이면 `diff`도 `null`.

---

### GET /reports/wallet-temperature
지갑 온도 상세 조회
(소비 상세 리포트 페이지)

Query Parameters:
- `year` (int)
- `month` (int)

Response:
```json
{
  "my_temp": 72,
  "peer_avg_temp": 65,
  "diff": 7,
  "level": "보통",
  "emoji": "😐",
  "message": "지갑이 적당히 데워지고 있어요. 이 흐름을 유지해보세요",
  "my_spent": 720000,
  "my_budget": 1000000,
  "peer_group": {
    "residence_type": "자취",
    "income_level": "30-60",
    "avg_usage_rate": 65.0
  },
  "temperature_levels": [
    { "min": 0,   "max": 19,  "emoji": "❄️", "label": "매우 안정", "status": "매우 안정", "message": "지갑이 시원하게 유지되고 있어요. 아직 충분히 여유 있어요" },
    { "min": 20,  "max": 49,  "emoji": "🙂", "label": "안정",     "status": "안정",     "message": "아직은 미지근한 상태! 여유 있게 잘 관리 중이에요" },
    { "min": 50,  "max": 79,  "emoji": "😐", "label": "보통",     "status": "보통",     "message": "지갑이 적당히 데워지고 있어요. 이 흐름을 유지해보세요" },
    { "min": 80,  "max": 99,  "emoji": "⚠️", "label": "임계",     "status": "주의",     "message": "열기가 꽤 올라왔어요. 거의 다 썼어요, 조심!" },
    { "min": 100, "max": 119, "emoji": "🔥", "label": "초과",     "status": "위험",     "message": "이미 끓어넘쳤어요. 불필요한 소비를 잠시 멈춰보세요" },
    { "min": 120, "max": null,"emoji": "🚨", "label": "과열",     "status": "매우 위험","message": "지갑이 타기 직전이에요. 지금 당장 지출을 멈추고 식혀야 해요" }
  ]
}
```

---

### GET /reports/bpti
BPTI 소비 성격 유형 상세 조회
(소비 상세 리포트 페이지)

Query Parameters:
- `year` (int)
- `month` (int)

Response:
```json
{
  "type": "FIRE",
  "label": "불지옥",
  "definition": "홧김 비용의 지배자",
  "message": "화가 날 때 지갑을 여는 타입! 스트레스 해소법을 돈 쓰기 말고 다른 걸로 찾아봐요.",
  "emotion_radar": {
    "스트레스": 40,
    "즉흥성": 20,
    "비교회피": 10,
    "충분한숙고": 20,
    "장기적가치": 10
  }
}
```

---

## 10. Reports — 내 소비 분석

### GET /reports/budget-status
나의 예산 현황 (주별 + 월별)

Query Parameters:
- `year` (int)
- `month` (int)

Response:
```json
{
  "monthly": {
    "budget": 1000000,
    "spent": 720000,
    "remaining": 280000,
    "usage_rate": 72.0
  },
  "weekly": {
    "current_week": 2,
    "budget": 250000,
    "spent": 180000,
    "remaining": 70000,
    "usage_rate": 72.0
  },
  "weekly_breakdown": [
    { "week": 1, "budget": 250000, "spent": 240000, "usage_rate": 96.0 },
    { "week": 2, "budget": 250000, "spent": 180000, "usage_rate": 72.0 },
    { "week": 3, "budget": 250000, "spent": 0,      "usage_rate": 0.0 },
    { "week": 4, "budget": 250000, "spent": 0,      "usage_rate": 0.0 }
  ]
}
```

---

### GET /reports/category
카테고리별 소비 조회 (도넛 그래프용)

Query Parameters:
- `year` (int)
- `month` (int)

Response:
```json
{
  "total_spent": 720000,
  "categories": [
    { "category": "식비",      "amount": 200000, "ratio": 27.8 },
    { "category": "고정지출",  "amount": 150000, "ratio": 20.8 },
    { "category": "교통",      "amount": 50000,  "ratio": 6.9  },
    { "category": "생활",      "amount": 80000,  "ratio": 11.1 },
    { "category": "쇼핑/패션", "amount": 120000, "ratio": 16.7 },
    { "category": "자기계발",  "amount": 40000,  "ratio": 5.6  },
    { "category": "문화/여가", "amount": 50000,  "ratio": 6.9  },
    { "category": "모임/기타", "amount": 30000,  "ratio": 4.2  }
  ]
}
```

---

### GET /reports/heatmap
시간대/요일별 소비 히트맵 조회

Query Parameters:
- `year` (int)
- `month` (int)

Response:
```json
{
  "heatmap": [
    { "day": "월", "time_slot": "아침",  "amount": 15000, "count": 3 },
    { "day": "월", "time_slot": "점심",  "amount": 30000, "count": 5 },
    { "day": "월", "time_slot": "저녁",  "amount": 45000, "count": 4 },
    { "day": "월", "time_slot": "밤",    "amount": 20000, "count": 2 },
    { "day": "월", "time_slot": "새벽",  "amount": 5000,  "count": 1 }
  ],
  "peak": {
    "day": "금",
    "time_slot": "밤",
    "notification_label": "불금 입구 컷"
  }
}
```

> `time_slot` 기준: 아침(06~11시), 점심(11~14시), 저녁(14~19시), 밤(19~23시), 새벽(23~06시)

---

### GET /reports/daily
일자별 수입/지출 합계 조회

Query Parameters:
- `year` (int)
- `month` (int)

Response:
```json
[
  { "date": "2026-07-01", "income": 0, "expense": 12000 },
  { "date": "2026-07-03", "income": 500000, "expense": 34000 }
]
```

---

### GET /reports/monthly-forecast
이번 달 예상 리포트 (AI 소비 예측)

Query Parameters:
- `year` (int)
- `month` (int)

Response:
```json
{
  "current_spent": 720000,
  "predicted_total": 980000,
  "budget": 1000000,
  "predicted_remaining": 20000,
  "is_over_budget": false,
  "confidence": "medium",
  "history": [
    { "year": 2026, "month": 4, "spent": 650000 },
    { "year": 2026, "month": 5, "spent": 810000 },
    { "year": 2026, "month": 6, "spent": 700000 },
    { "year": 2026, "month": 7, "spent": 890000 }
  ],
  "monthly_average": 762500
}
```

> `history`: 조회 월을 제외한 과거 4개월 실제 지출액, 오래된 순 (막대 차트용).
> `monthly_average`: `history` 4개월의 평균 지출액.

---

### GET /reports/wallet-temperature/monthly
이번 달 지갑 현황 (월간 온도 요약)

Query Parameters:
- `year` (int)
- `month` (int)

Response:
```json
{
  "my_temp": 72,
  "peer_avg_temp": 65,
  "level": "보통",
  "emoji": "😐",
  "message": "지갑이 적당히 데워지고 있어요. 이 흐름을 유지해보세요",
  "weekly_temps": [
    { "week": 1, "temp": 96 },
    { "week": 2, "temp": 72 },
    { "week": 3, "temp": 0  },
    { "week": 4, "temp": 0  }
  ]
}
```

---

## 11. Notes

- 모든 엔드포인트는 JWT 인증 필요 (`Authorization: Bearer <token>`)
- 날짜 형식: `YYYY-MM-DD`
- 시간 형식: `HH:mm`
- `income_level` 값: `"under-30"` | `"30-60"` | `"60-100"` | `"over-100"`
- `residence_type` 값: `"자취"` | `"기숙사"` | `"통학"`
- `type` (거래) 값: `"income"` | `"expense"`
