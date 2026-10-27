from pydantic_settings import BaseSettings, SettingsConfigDict
from pydantic import computed_field


class Settings(BaseSettings):
    PROJECT_NAME: str = "API Plataforma Hotelera Oruro PDHO"
    API_V1_STR: str = "/api/v1"
    
    # Seguridad JWT y AGETIC
    SECRET_KEY: str = "pdho_seguridad_plataforma_hotelera_oruro_secret_key_2026"
    ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 60 * 8  # 8 horas por jornada laboral
    
    # Base de Datos PostgreSQL
    DB_NAME: str = "DB_PDHO"
    DB_HOST: str = "localhost"
    DB_USER: str = "postgres"
    DB_PASS: str = "postgres"
    DB_PORT: int = 5432
    
    # Correo Electrónico
    EMAIL_HOST: str = "smtp.gmail.com"
    EMAIL_USE_TLS: bool = True
    EMAIL_PORT: int = 587
    EMAIL_HOST_USER: str = ""
    EMAIL_HOST_PASSWORD: str = ""
    
    # CORS
    BACKEND_CORS_ORIGINS: list[str] = ["http://localhost:4200", "http://127.0.0.1:4200"]
    
    # Credenciales iniciales para scripts de inicialización / Semilla
    ADMIN_EMAIL: str = "admin@oruro.gob.bo"
    ADMIN_PASSWORD: str = "AdminOruro2026!"
    
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore"
    )

    @computed_field
    @property
    def ASYNC_DATABASE_URL(self) -> str:
        return f"postgresql+asyncpg://{self.DB_USER}:{self.DB_PASS}@{self.DB_HOST}:{self.DB_PORT}/{self.DB_NAME}"

    @computed_field
    @property
    def SYNC_DATABASE_URL(self) -> str:
        return f"postgresql://{self.DB_USER}:{self.DB_PASS}@{self.DB_HOST}:{self.DB_PORT}/{self.DB_NAME}"


settings = Settings()
