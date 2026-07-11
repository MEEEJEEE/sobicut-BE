from pydantic import BaseModel, Field


class WeeklyBudgets(BaseModel):
    week_1: int = Field(ge=0)
    week_2: int = Field(ge=0)
    week_3: int = Field(ge=0)
    week_4: int = Field(ge=0)


class BudgetOut(BaseModel):
    monthly_budget: int
    weekly_budget: int
    weekly_budgets: WeeklyBudgets


class BudgetUpdate(BaseModel):
    monthly_budget: int = Field(ge=0)
    weekly_budget: int = Field(ge=0)
    weekly_budgets: WeeklyBudgets
