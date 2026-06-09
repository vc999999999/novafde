import os
import subprocess
from pathlib import Path

from fastapi.testclient import TestClient

from app.main import create_app
from app.settings import Settings


PROJECT_ROOT = Path(__file__).resolve().parents[2]


def test_cli_command_contract_api_lists_safe_local_commands(tmp_path: Path) -> None:
    client = TestClient(create_app(Settings(data_dir=tmp_path)))

    response = client.get("/api/cli/commands")
    assert response.status_code == 200
    commands = response.json()
    names = {command["name"] for command in commands}
    assert {"install", "run", "doctor", "setup-llm", "clean-artifacts", "config set", "config test"}.issubset(names)

    setup_command = next(command for command in commands if command["name"] == "setup-llm")
    assert setup_command["command"] == "sh scripts/setup-llm.sh"
    assert setup_command["repeatable"] is True
    assert ".env" in setup_command["writes"]
    assert "config/providers.local.json" in setup_command["writes"]
    assert setup_command["dangerLevel"] == "low"


def test_required_shell_scripts_have_help_and_do_not_print_or_delete_keys() -> None:
    script_names = ["install.sh", "run.sh", "setup-llm.sh", "doctor.sh", "clean-artifacts.sh"]
    for script_name in script_names:
        script_path = PROJECT_ROOT / "scripts" / script_name
        assert script_path.exists()
        content = script_path.read_text(encoding="utf-8")
        assert "set -euo pipefail" in content
        assert "API Key" not in content

        result = subprocess.run(
            ["sh", str(script_path), "--help"],
            cwd=PROJECT_ROOT,
            text=True,
            capture_output=True,
            check=False,
        )
        assert result.returncode == 0
        assert "Usage:" in result.stdout

    clean_content = (PROJECT_ROOT / "scripts" / "clean-artifacts.sh").read_text(encoding="utf-8")
    assert "skillforge.sqlite3" not in clean_content
    assert "providers.local.json" not in clean_content


def test_run_script_loads_dotenv_before_starting_backend() -> None:
    run_content = (PROJECT_ROOT / "scripts" / "run.sh").read_text(encoding="utf-8")
    assert ". ./.env" in run_content
    assert run_content.index(". ./.env") < run_content.index("python3 -m uvicorn")


def test_skillforge_wrapper_help_lists_config_and_generation_commands() -> None:
    wrapper = PROJECT_ROOT / "skillforge"
    assert wrapper.exists()

    result = subprocess.run(
        ["sh", str(wrapper), "--help"],
        cwd=PROJECT_ROOT,
        text=True,
        capture_output=True,
        check=False,
        env={**os.environ, "PYTHONUNBUFFERED": "1"},
    )
    assert result.returncode == 0
    assert "skillforge config test" in result.stdout
    assert "skillforge generate" in result.stdout
    assert "skillforge package" in result.stdout
