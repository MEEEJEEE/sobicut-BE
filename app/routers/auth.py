from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.core.deps import get_current_token, get_current_user
from app.core.security import (
    PASSWORD_RULE_MESSAGE,
    create_access_token,
    hash_password,
    is_valid_password,
    verify_password,
)
from app.db.session import get_db
from app.models import TokenBlacklist, User
from app.schemas.auth import (
    CheckEmailRequest,
    CheckEmailResponse,
    KakaoLoginRequest,
    KakaoLoginResponse,
    LoginRequest,
    LoginResponse,
    MessageResponse,
    SignupRequest,
    SignupResponse,
    ValidatePasswordRequest,
    ValidatePasswordResponse,
    WithdrawRequest,
)
from app.services.kakao_auth import KakaoAuthError, fetch_kakao_user

router = APIRouter(prefix="/auth", tags=["Auth"])

RESIDENCE_TYPES = {"자취", "기숙사", "통학"}
INCOME_LEVELS = {"under-30", "30-60", "60-100", "over-100"}


@router.post("/signup", response_model=SignupResponse, status_code=status.HTTP_201_CREATED)
def signup(body: SignupRequest, db: Session = Depends(get_db)):
    if body.residence_type not in RESIDENCE_TYPES:
        raise HTTPException(status_code=422, detail="거주형태는 자취/기숙사/통학 중 하나여야 합니다.")
    if body.income_level not in INCOME_LEVELS:
        raise HTTPException(status_code=422, detail="소득구간 값이 올바르지 않습니다.")
    if not is_valid_password(body.password):
        raise HTTPException(status_code=422, detail=PASSWORD_RULE_MESSAGE)
    if db.query(User).filter(User.email == body.email, User.deleted_at.is_(None)).first():
        raise HTTPException(status_code=409, detail="이미 사용 중인 이메일입니다.")

    user = User(
        email=body.email,
        password=hash_password(body.password),
        nickname=body.nickname,
        residence_type=body.residence_type,
        income_level=body.income_level,
    )
    db.add(user)
    db.commit()
    db.refresh(user)
    return SignupResponse(id=user.id, email=user.email)


@router.post("/login", response_model=LoginResponse)
def login(body: LoginRequest, db: Session = Depends(get_db)):
    user = db.query(User).filter(User.email == body.email, User.deleted_at.is_(None)).first()
    if user is None:
        raise HTTPException(status_code=404, detail="존재하지 않는 사용자입니다.")
    if user.password is None:
        raise HTTPException(status_code=401, detail="카카오 로그인으로 가입된 계정입니다. 카카오 로그인을 이용해주세요.")
    if not verify_password(body.password, user.password):
        raise HTTPException(status_code=401, detail="비밀번호가 올바르지 않습니다.")
    return LoginResponse(access_token=create_access_token(user.id))


@router.post("/kakao", response_model=KakaoLoginResponse)
def kakao_login(body: KakaoLoginRequest, db: Session = Depends(get_db)):
    try:
        kakao_info = fetch_kakao_user(body.access_token)
    except KakaoAuthError:
        raise HTTPException(status_code=401, detail="유효하지 않은 카카오 액세스 토큰입니다.")

    kakao_id = kakao_info["kakao_id"]
    email = kakao_info.get("email")

    user = db.query(User).filter(User.kakao_id == kakao_id, User.deleted_at.is_(None)).first()
    is_new_user = False

    if user is None and email and kakao_info.get("email_verified"):
        # 이메일 인증된 카카오 계정이 기존 일반(이메일/비밀번호) 가입 계정과 이메일이 같으면 자동 연동
        existing = db.query(User).filter(User.email == email, User.deleted_at.is_(None)).first()
        if existing is not None:
            existing.kakao_id = kakao_id
            user = existing

    if user is None:
        if not email:
            raise HTTPException(status_code=422, detail="카카오 계정에서 이메일 제공에 동의해야 가입할 수 있습니다.")
        if db.query(User).filter(User.email == email, User.deleted_at.is_(None)).first():
            raise HTTPException(status_code=409, detail="이미 사용 중인 이메일입니다.")
        if not body.nickname or body.residence_type not in RESIDENCE_TYPES or body.income_level not in INCOME_LEVELS:
            raise HTTPException(
                status_code=422,
                detail="최초 카카오 로그인 시 nickname/residence_type/income_level이 필요합니다.",
            )
        user = User(
            email=email,
            password=None,
            kakao_id=kakao_id,
            nickname=body.nickname,
            residence_type=body.residence_type,
            income_level=body.income_level,
        )
        db.add(user)
        is_new_user = True

    db.commit()
    db.refresh(user)
    return KakaoLoginResponse(access_token=create_access_token(user.id), is_new_user=is_new_user)


@router.get("/logout", response_model=MessageResponse)
def logout(
    token: str = Depends(get_current_token),
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    db.add(TokenBlacklist(token=token))
    db.commit()
    return MessageResponse(message="로그아웃 완료")


@router.patch("/withdraw", response_model=MessageResponse)
def withdraw(
    body: WithdrawRequest,
    token: str = Depends(get_current_token),
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    if user.password is not None and not verify_password(body.password, user.password):
        raise HTTPException(status_code=401, detail="비밀번호가 올바르지 않습니다.")
    user.deleted_at = datetime.now()
    db.add(TokenBlacklist(token=token))
    db.commit()
    return MessageResponse(message="탈퇴 완료")


@router.post("/check-email", response_model=CheckEmailResponse)
def check_email(body: CheckEmailRequest, db: Session = Depends(get_db)):
    exists = (
        db.query(User).filter(User.email == body.email, User.deleted_at.is_(None)).first() is not None
    )
    return CheckEmailResponse(is_available=not exists)


@router.post("/validate-password", response_model=ValidatePasswordResponse)
def validate_password(body: ValidatePasswordRequest):
    valid = is_valid_password(body.password)
    return ValidatePasswordResponse(
        is_valid=valid,
        message="사용 가능한 비밀번호입니다." if valid else PASSWORD_RULE_MESSAGE,
    )
