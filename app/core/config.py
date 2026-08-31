from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """환경 변수 기반 설정 (.env 파일 사용)"""

    DATABASE_URL: str = "sqlite:///./sobicut.db"
    SECRET_KEY: str = "dev-secret-key-change-in-production"
    ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 60 * 24  # 24시간

    # 충동 위험 지수 3단계 임계값 (설문조사 기반 충동 점수 로직 재설정 문서 기준)
    # 0~59 낮음 / 60~66 주의 / 67 이상 경고
    IMPULSE_WARNING_THRESHOLD: float = 0.67
    IMPULSE_CAUTION_THRESHOLD: float = 0.60
    # 고가 소비 기준 (만족도 조사 대상)
    HIGH_PRICE_THRESHOLD: int = 50000

    # CORS 허용 origin (콤마로 구분, 프론트 개발 서버 기본값)
    CORS_ORIGINS: str = "http://localhost:5173,http://127.0.0.1:5173"

    # 웹 푸시 VAPID 키 (`python scripts/generate_vapid_keys.py`로 생성)
    VAPID_PUBLIC_KEY: str = ""
    VAPID_PRIVATE_KEY: str = ""
    VAPID_CLAIMS_EMAIL: str = "admin@sobicut.app"

    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    @property
    def cors_origins(self) -> list[str]:
        return [origin.strip() for origin in self.CORS_ORIGINS.split(",") if origin.strip()]


settings = Settings()
