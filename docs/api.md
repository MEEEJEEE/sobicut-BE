
# API Specification

## 1. Overview
Emotion-based spending analysis API

Base URL:

---

## 2. Authentication

### POST /auth/signup
Create a new user

Request:
```json
{
  "email": "test@test.com",
  "password": "1234",
  "nickname": "user1",
  "residence_type": "자취",
  "income_level": "중"
}
````

Response:

```json
{
  "id": 1,
  "email": "test@test.com"
}
```

---

### POST /auth/login

Login user

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

## 3. Transactions

### POST /transactions

Create income or expense

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

Get all transactions

---

### GET /transactions/{id}

Get transaction detail

---

### PUT /transactions/{id}

Update transaction

---

### DELETE /transactions/{id}

Delete transaction

---

## 4. Emotion

### POST /transactions/{id}/emotions

Add emotion tags to a transaction

Request:

```json
{
  "emotion_tag_ids": [1, 2]
}
```

---

## 5. Budget

### GET /budget

Get user budget

Response:

```json
{
  "monthly_budget": 1000000,
  "weekly_budget": 250000
}
```

---

### PUT /budget

Update budget

Request:

```json
{
  "monthly_budget": 1000000,
  "weekly_budget": 250000
}
```

---

## 6. Satisfaction

### POST /satisfactions

Create satisfaction record

Request:

```json
{
  "transaction_id": 1,
  "day_type": "7일",
  "score": 3
}
```

---

## 7. Notifications

### GET /notifications

Get notifications

Response:

```json
[
  {
    "id": 1,
    "title": "지출 경고",
    "message": "이번 주 예산을 초과했습니다.",
    "is_read": false
  }
]
```

---

### PUT /notifications/{id}

Mark notification as read

---

## 8. Reports

### GET /reports/summary

Get summary report

Response:

```json
{
  "total_spent": 300000,
  "remaining_budget": 200000,
  "impulse_score": 72,
  "wallet_temperature": "HOT"
}
```

---

## 9. Notes

* All endpoints require authentication (JWT)
* Date format: YYYY-MM-DD
* Time format: HH:mm

```
```
