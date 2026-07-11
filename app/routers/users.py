from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.core.deps import get_current_user
from app.core.security import (
    PASSWORD_RULE_MESSAGE,
    hash_password,
    is_valid_password,
    verify_password,
)
from app.db.session import get_db
from app.models import User
from app.routers.auth import INCOME_LEVELS, RESIDENCE_TYPES
from app.schemas.auth import MessageResponse
from app.schemas.user import (
    IncomeLevelUpdate,
    LevelOut,
    NicknameUpdate,
    PasswordUpdate,
    ResidenceTypeUpdate,
    UserProfileOut,
    UserSettingsOut,
)
from app.services.level import get_level_info

router = APIRouter(prefix="/users", tags=["My Page"])


@router.get("/me", response_model=UserProfileOut)
def get_me(user: User = Depends(get_current_user)):
    return user


@router.get("/me/level", response_model=LevelOut)
def get_my_level(user: User = Depends(get_current_user)):
    return get_level_info(user)


@router.get("/me/settings", response_model=UserSettingsOut)
def get_my_settings(user: User = Depends(get_current_user)):
    return user


@router.patch("/me/nickname", response_model=MessageResponse)
def update_nickname(
    body: NicknameUpdate,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    if not body.nickname.strip():
        raise HTTPException(status_code=422, detail="닉네임을 입력해주세요.")
    user.nickname = body.nickname.strip()
    db.commit()
    return MessageResponse(message="닉네임 변경 완료")


@router.patch("/me/password", response_model=MessageResponse)
def update_password(
    body: PasswordUpdate,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    if not verify_password(body.current_password, user.password):
        raise HTTPException(status_code=401, detail="현재 비밀번호가 올바르지 않습니다.")
    if not is_valid_password(body.new_password):
        raise HTTPException(status_code=422, detail=PASSWORD_RULE_MESSAGE)
    user.password = hash_password(body.new_password)
    db.commit()
    return MessageResponse(message="비밀번호 변경 완료")


@router.patch("/me/residence-type", response_model=MessageResponse)
def update_residence_type(
    body: ResidenceTypeUpdate,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    if body.residence_type not in RESIDENCE_TYPES:
        raise HTTPException(status_code=422, detail="거주형태는 자취/기숙사/통학 중 하나여야 합니다.")
    user.residence_type = body.residence_type
    db.commit()
    return MessageResponse(message="거주형태 변경 완료")


@router.patch("/me/income-level", response_model=MessageResponse)
def update_income_level(
    body: IncomeLevelUpdate,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    if body.income_level not in INCOME_LEVELS:
        raise HTTPException(status_code=422, detail="소득구간 값이 올바르지 않습니다.")
    user.income_level = body.income_level
    db.commit()
    return MessageResponse(message="소득구간 변경 완료")
