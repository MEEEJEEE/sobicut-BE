from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """환경 변수 기반 설정 (.env 파일 사용)"""

    DATABASE_URL: str = "sqlite:///./sobicut.db"
    SECRET_KEY: str = "dev-secret-key-change-in-production"
    ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 60 * 24  # 24시간

    # 충동 소비 판단 임계값 (확률)
    IMPULSE_THRESHOLD: float = 0.75
    # 고가 소비 기준 (만족도 조사 대상)
    HIGH_PRICE_THRESHOLD: int = 50000

    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")


settings = Settings()
