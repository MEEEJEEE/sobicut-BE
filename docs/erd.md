# ERD (Entity Relationship Diagram)

## 1. Overview
This project analyzes user spending behavior by incorporating emotional factors.

Core Flow:
User → Transaction → Emotion → Analysis

---

## 2. Entities

### User
- id (PK)
- email
- password
- nickname
- residence_type
- income_level
- created_at

### Transaction
- id (PK)
- user_id (FK)
- amount
- type (income / expense)
- category
- merchant
- description
- transaction_date
- transaction_time
- created_at

### EmotionTag
- id (PK)
- name

### TransactionEmotion
- id (PK)
- transaction_id (FK)
- emotion_tag_id (FK)

### Budget
- id (PK)
- user_id (FK)
- monthly_budget
- weekly_budget

### Satisfaction
- id (PK)
- transaction_id (FK)
- day_type
- score

### Notification
- id (PK)
- user_id (FK)
- title
- message
- type
- is_read
- created_at

---

## 3. Relationships

- User 1 : N Transaction
- Transaction N : M EmotionTag
- Transaction 1 : N Satisfaction
- User 1 : 1 Budget
- User 1 : N Notification

---

## 4. ERD Diagram (Mermaid)

```mermaid
erDiagram
    USERS ||--o{ TRANSACTIONS : has
    USERS ||--|| BUDGETS : owns
    USERS ||--o{ NOTIFICATIONS : receives

    TRANSACTIONS ||--o{ TRANSACTION_EMOTIONS : mapped
    EMOTION_TAGS ||--o{ TRANSACTION_EMOTIONS : mapped
    TRANSACTIONS ||--o{ SATISFACTIONS : has

    USERS {
        int id
        string email
        string password
        string nickname
        string residence_type
        string income_level
        datetime created_at
    }

    TRANSACTIONS {
        int id
        int user_id
        int amount
        string type
        string category
        string merchant
        string description
        date transaction_date
        time transaction_time
        datetime created_at
    }

    EMOTION_TAGS {
        int id
        string name
    }

    TRANSACTION_EMOTIONS {
        int id
        int transaction_id
        int emotion_tag_id
    }

    BUDGETS {
        int id
        int user_id
        int monthly_budget
        int weekly_budget
    }

    SATISFACTIONS {
        int id
        int transaction_id
        string day_type
        int score
    }

    NOTIFICATIONS {
        int id
        int user_id
        string title
        string message
        string type
        boolean is_read
        datetime created_at
    }
