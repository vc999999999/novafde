from pathlib import Path
from typing import Literal
from pydantic import BaseModel, Field, model_validator


class Settings(BaseModel):
    bind_host: Literal["127.0.0.1"] = "127.0.0.1"
    data_dir: Path = Field(default=Path("backend/.data"))
    database_name: str = "skillforge.sqlite3"
    artifact_dir_name: str = "artifacts"
    attempt_retention_days: int = Field(default=30, ge=1, le=365)
    max_run_tokens: int = Field(default=200_000, ge=1)
    max_run_cost_usd: float = Field(default=10.0, gt=0)
    max_run_duration_seconds: int = Field(default=600, ge=1)
    provider_config_path: Path = Field(default=Path("config/providers.local.json"))
    use_system_keyring: bool = True
    cors_origins: list[str] = Field(
        default_factory=lambda: [
            "http://localhost:5173",
            "http://127.0.0.1:5173",
            "http://localhost:3000",
            "http://127.0.0.1:3000",
        ]
    )

    @model_validator(mode="after")
    def reject_wildcard_cors_with_credentials(self) -> "Settings":
        if "*" in self.cors_origins:
            import logging
            logging.getLogger(__name__).warning(
                "CORS allow_origins contains '*' which is insecure when used with "
                "allow_credentials=True. Restrict cors_origins to specific origins."
            )
        return self

    @property
    def database_path(self) -> Path:
        return self.data_dir / self.database_name

    @property
    def artifact_root(self) -> Path:
        return self.data_dir / self.artifact_dir_name

    @property
    def encrypted_secrets_path(self) -> Path:
        return self.data_dir / "provider-secrets.enc"

    @property
    def secret_key_path(self) -> Path:
        return self.data_dir / ".provider-secrets.key"
