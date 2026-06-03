from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    database_url: str = "postgresql+asyncpg://postgres:postgres@localhost:5432/ev_charger"
    database_url_sync: str = "postgresql+psycopg2://postgres:postgres@localhost:5432/ev_charger"
    jwt_secret: str = "change-me-in-production"
    jwt_algorithm: str = "HS256"
    access_token_expire_minutes: int = 30
    refresh_token_expire_days: int = 7
    nordpool_price_area: str = "NL"
    # Price source: "energyzero" (real NL consumer prices incl. BTW) or "nordpool"
    price_source: str = "energyzero"
    cors_origins: list[str] = ["*"]

    class Config:
        env_file = ".env"


settings = Settings()
