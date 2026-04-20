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

## 4. Emotion

### GET /emotions
감정 태그 목록 전체 조회

Response:
```json
[
  { "id": 1, "name": "스트레스", "type": "negative" },
  { "id": 2, "name": "무의식",   "type": "negative" },
  { "id": 3, "name": "귀찮음",   "type": "negative" },
  { "id": 4, "name": "성취",     "type": "positive" },
  { "id": 5, "name": "행복",     "type": "positive" },
  { "id": 6, "name": "고마움",   "type": "positive" }
]
```

---

### POST /transactions/{id}/emotions
거래에 감정 태그 등록

Request:
```json
{
  "emotion_tag_ids": [1, 2]
}
```

Response:
```json
{
  "message": "감정 태그 등록 완료"
}
```

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
만족도 등록 (5만원 이상 고가 소비, 7일/30일 후 2회 입력)

Request:
```json
{
  "transaction_id": 1,
  "day_type": "7일",
  "score": 3
}
```

> `day_type`: `"7일"` | `"30일"`
> `score`: 1(매우 후회) ~ 5(매우 만족)

Response:
```json
{
  "id": 1,
  "message": "만족도 등록 완료"
}
```

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

## 7. Notifications

### GET /notifications
알림 목록 조회

Query Parameters:
- `type` (string, optional): 알림 종류 필터
  - `budget_weekly`: 주간 예산 초과
  - `budget_monthly`: 월간 예산 초과
  - `impulse_warning`: 충동 소비 경고
  - `heatmap_time`: 시간대 소비 패턴 경고
  - `heatmap_day`: 요일 소비 패턴 경고
  - `satisfaction_request`: 만족도 입력 요청

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
  "level": 3,
  "level_name": "몬스터",
  "current_exp": 420,
  "next_level_exp": 600,
  "description": "소비 습관이 조금씩 성장하고 있어요!"
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
    "무의식": 0.2,
    "귀찮음": 0.1,
    "성취": 0.1,
    "행복": 0.1,
    "고마움": 0.1
  },
  "top_impulse_transactions": [
    {
      "id": 3,
      "merchant": "쿠팡",
      "amount": 45000,
      "transaction_date": "2026-04-15",
      "impulse_score": 88
    }
  ]
}
```

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
    "avg_spent": 650000,
    "avg_budget": 1000000
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
    "무의식": 20,
    "귀찮음": 10,
    "성취": 10,
    "행복": 15,
    "고마움": 5
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
  "confidence": "medium"
}
```

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
