from fastapi import FastAPI
from pydantic import BaseModel
from typing import List, Optional
from datetime import datetime

app = FastAPI(
    title="가계부 API",
    description="FastAPI로 만든 간단한 가계부 CRUD",
    version="1.0.0"
)

# =========================
# 📌 데이터 모델
# =========================
class Expense(BaseModel):
    id: Optional[int] = None
    amount: int
    category: str
    datetime: datetime
    merchant: Optional[str] = None
    emotion_tag: Optional[str] = None


# =========================
# 📌 메모리 DB (임시 저장)
# =========================
db: List[Expense] = []


# =========================
# 📌 기본 테스트
# =========================
@app.get("/")
def root():
    return {
        "message": "FastAPI 가계부 서버 실행 완료"
    }


# =========================
# 📌 CREATE (지출 추가)
# =========================
@app.post("/expenses")
def create_expense(expense: Expense):
    expense.id = len(db) + 1
    db.append(expense)

    return {
        "success": True,
        "message": "지출 등록 완료",
        "data": expense
    }


# =========================
# 📌 READ ALL (전체 조회)
# =========================
@app.get("/expenses")
def get_expenses():
    return {
        "success": True,
        "data": db
    }


# =========================
# 📌 READ ONE (단건 조회)
# =========================
@app.get("/expenses/{expense_id}")
def get_expense(expense_id: int):
    for expense in db:
        if expense.id == expense_id:
            return {
                "success": True,
                "data": expense
            }

    return {
        "success": False,
        "message": "데이터 없음"
    }


# =========================
# 📌 UPDATE (수정)
# =========================
@app.put("/expenses/{expense_id}")
def update_expense(expense_id: int, updated: Expense):
    for i, expense in enumerate(db):
        if expense.id == expense_id:
            updated.id = expense_id
            db[i] = updated

            return {
                "success": True,
                "message": "수정 완료",
                "data": updated
            }

    return {
        "success": False,
        "message": "데이터 없음"
    }


# =========================
# 📌 DELETE (삭제)
# =========================
@app.delete("/expenses/{expense_id}")
def delete_expense(expense_id: int):
    for i, expense in enumerate(db):
        if expense.id == expense_id:
            db.pop(i)

            return {
                "success": True,
                "message": "삭제 완료"
            }

    return {
        "success": False,
        "message": "데이터 없음"
    }
