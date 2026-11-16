from pydantic_settings import BaseSettings

class Settings(BaseSettings):
    DATABASE_URL: str = "postgresql+asyncpg://postgres:secret_password@db:5432/quakewatch"
    REDIS_URL: str = "redis://redis:6379/0"
    JWT_SECRET: str = "super_secret_key_for_baikal_2026"
    JWT_ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 120
    DATA_DIR: str = "/app/data"

    S3_ENDPOINT: str = "http://minio:9000"
    S3_ACCESS_KEY: str = "minioadmin"
    S3_SECRET_KEY: str = "minioadmin_password"
    S3_BUCKET: str = "quakewatch-data"

settings = Settings()
