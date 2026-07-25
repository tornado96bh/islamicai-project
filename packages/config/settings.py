from functools import lru_cache
from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict

class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")
    POSTGRES_HOST: str = Field(default="localhost")
    POSTGRES_PORT: int = Field(default=5432)
    POSTGRES_DB: str = Field(default="islamicai")
    POSTGRES_USER: str = Field(default="islamicai")
    POSTGRES_PASSWORD: str = Field(default="change_me")
    REDIS_PORT: int = Field(default=6379)
    MINIO_ROOT_USER: str = Field(default="minio")
    MINIO_ROOT_PASSWORD: str = Field(default="change_me_too")
    MINIO_PORT: int = Field(default=9000)
    MINIO_CONSOLE_PORT: int = Field(default=9001)
    QDRANT_PORT: int = Field(default=6333)
    NEO4J_HTTP_PORT: int = Field(default=7474)
    NEO4J_BOLT_PORT: int = Field(default=7687)
    BACKEND_PORT: int = Field(default=8000)

    @property
    def database_url(self) -> str:
        return f"postgresql+psycopg://{self.POSTGRES_USER}:{self.POSTGRES_PASSWORD}@{self.POSTGRES_HOST}:{self.POSTGRES_PORT}/{self.POSTGRES_DB}"

@lru_cache(maxsize=1)
def get_settings() -> Settings:
    return Settings()

settings = get_settings()
