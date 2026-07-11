from datetime import datetime

from pydantic import BaseModel, ConfigDict


class UserProfileOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    email: str
    nickname: str
    residence_type: str
    income_level: str
    created_at: datetime


class UserSettingsOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    email: str
    nickname: str
    residence_type: str
    income_level: str


class LevelOut(BaseModel):
    level: int
    level_name: str
    current_exp: int
    next_level_exp: int | None
    description: str


class NicknameUpdate(BaseModel):
    nickname: str


class PasswordUpdate(BaseModel):
    current_password: str
    new_password: str


class ResidenceTypeUpdate(BaseModel):
    residence_type: str


class IncomeLevelUpdate(BaseModel):
    income_level: str
