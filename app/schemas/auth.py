from pydantic import BaseModel, EmailStr


class SignupRequest(BaseModel):
    email: EmailStr
    password: str
    nickname: str
    residence_type: str  # 자취 | 기숙사 | 통학
    income_level: str  # under-30 | 30-60 | 60-100 | over-100


class SignupResponse(BaseModel):
    id: int
    email: EmailStr


class LoginRequest(BaseModel):
    email: EmailStr
    password: str


class LoginResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"


class WithdrawRequest(BaseModel):
    password: str


class CheckEmailRequest(BaseModel):
    email: EmailStr


class CheckEmailResponse(BaseModel):
    is_available: bool


class ValidatePasswordRequest(BaseModel):
    password: str


class ValidatePasswordResponse(BaseModel):
    is_valid: bool
    message: str


class MessageResponse(BaseModel):
    message: str
