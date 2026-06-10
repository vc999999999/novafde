from pathlib import Path

from fastapi.testclient import TestClient
import pytest
from pydantic import ValidationError

from app.main import create_app
from app.settings import Settings


def test_runtime_info_declares_local_only_sqlite_and_loopback(tmp_path: Path) -> None:
    settings = Settings(data_dir=tmp_path)
    client = TestClient(create_app(settings))

    response = client.get("/api/runtime")

    assert response.status_code == 200
    assert response.json() == {
        "mode": "local",
        "database": "sqlite",
        "loopbackOnly": True,
        "bindHost": "127.0.0.1",
    }
    assert settings.database_path.suffix == ".sqlite3"
    assert settings.bind_host == "127.0.0.1"

    with pytest.raises(ValidationError):
        Settings(data_dir=tmp_path, bind_host="0.0.0.0")


def test_startup_marks_unfinished_generation_as_interrupted(tmp_path: Path) -> None:
    settings = Settings(data_dir=tmp_path)
    first_app = create_app(settings)
    first_service = first_app.state.service
    generation = first_service.storage.create_generation_shell(
        generation_id="gen_interrupted",
        draft_id="draft_1",
        started_at=1,
    )
    assert generation.status == "queued"

    second_app = create_app(settings)
    restored = second_app.state.service.get_generation("gen_interrupted")

    assert restored is not None
    assert restored.status == "interrupted"
    assert restored.completedAt is not None
