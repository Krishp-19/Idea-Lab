from functools import lru_cache
from pathlib import Path
from typing import List
from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    app_name: str = "Two-Wheeler Illegal Parking Detection System"
    api_v1_prefix: str = "/api/v1"
    debug: bool = False

    # Database
    database_url: str = Field(
        default="postgresql+psycopg://parking:parking@localhost:5432/parking_db",
        alias="DATABASE_URL",
    )

    # Security
    secret_key: str = Field(default="dev-secret-key-change-in-production-123456", alias="SECRET_KEY")
    access_token_expire_minutes: int = 480
    algorithm: str = "HS256"

    # CORS
    cors_origins: str = Field(
        default="http://localhost:3000,http://localhost:5173,http://localhost:8080,http://frontend:80",
        alias="CORS_ORIGINS",
    )

    # Storage and paths
    evidence_dir: str = Field(default="data/evidence", alias="EVIDENCE_DIR")
    features_csv: str = Field(default="data/features/features.csv", alias="FEATURES_CSV")
    zone_config_path: str = Field(default="config/zones.json", alias="ZONE_CONFIG_PATH")
    pipeline_config_path: str = Field(default="config/pipeline.yaml", alias="PIPELINE_CONFIG_PATH")
    trained_models_dir: str = Field(default="data/trained_models", alias="TRAINED_MODELS_DIR")

    # Initial admin
    default_admin_username: str = "admin"
    default_admin_password: str = "Admin@123456"

    # ML Knobs
    yolo_model: str = Field(default="yolov8n.pt", alias="YOLO_MODEL")
    device: str = Field(default="cpu", alias="DEVICE")
    confidence_threshold: float = Field(default=0.40, alias="CONFIDENCE_THRESHOLD")
    dwell_time_seconds: int = Field(default=30, alias="DWELL_TIME_SECONDS")

    @property
    def cors_origin_list(self) -> List[str]:
        return [x.strip() for x in self.cors_origins.split(",") if x.strip()]


@lru_cache
def get_settings() -> Settings:
    return Settings()
