from pathlib import Path
from pydantic import BaseModel, Field


class Settings(BaseModel):
    data_dir: Path = Field(default=Path("backend/.data"))
    database_name: str = "skillforge.sqlite3"
    artifact_dir_name: str = "artifacts"
    provider_config_path: Path = Field(default=Path("config/providers.local.json"))
    env_path: Path = Field(default=Path(".env"))
    cors_origins: list[str] = Field(
        default_factory=lambda: [
            "http://localhost:5173",
            "http://127.0.0.1:5173",
            "http://localhost:3000",
            "http://127.0.0.1:3000",
        ]
    )

    @property
    def database_path(self) -> Path:
        return self.data_dir / self.database_name

    @property
    def artifact_root(self) -> Path:
        return self.data_dir / self.artifact_dir_name
