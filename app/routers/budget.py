from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.core.deps import get_current_user
from app.db.session import get_db
from app.models import Budget, User
from app.schemas.budget import BudgetOut, BudgetUpdate, WeeklyBudgets

router = APIRouter(prefix="/budget", tags=["Budget"])


def _to_out(budget: Budget) -> BudgetOut:
    return BudgetOut(
        monthly_budget=budget.monthly_budget,
        weekly_budget=budget.weekly_budget,
        weekly_budgets=WeeklyBudgets(
            week_1=budget.week_1_budget,
            week_2=budget.week_2_budget,
            week_3=budget.week_3_budget,
            week_4=budget.week_4_budget,
        ),
    )


@router.get("", response_model=BudgetOut)
def get_budget(user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    budget = db.query(Budget).filter(Budget.user_id == user.id).first()
    if budget is None:
        budget = Budget(user_id=user.id)  # 기본값 0
        db.add(budget)
        db.commit()
        db.refresh(budget)
    return _to_out(budget)


@router.put("", response_model=BudgetOut)
def update_budget(
    body: BudgetUpdate,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    budget = db.query(Budget).filter(Budget.user_id == user.id).first()
    if budget is None:
        budget = Budget(user_id=user.id)
        db.add(budget)

    budget.monthly_budget = body.monthly_budget
    budget.weekly_budget = body.weekly_budget
    budget.week_1_budget = body.weekly_budgets.week_1
    budget.week_2_budget = body.weekly_budgets.week_2
    budget.week_3_budget = body.weekly_budgets.week_3
    budget.week_4_budget = body.weekly_budgets.week_4
    db.commit()
    db.refresh(budget)
    return _to_out(budget)
