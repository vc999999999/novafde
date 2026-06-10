from __future__ import annotations

import json
import os
from pathlib import Path

from cryptography.fernet import Fernet, InvalidToken


class SecretStore:
    def __init__(
        self,
        *,
        encrypted_path: Path,
        key_path: Path,
        prefer_keyring: bool = True,
        service_name: str = "novafde",
    ) -> None:
        self.encrypted_path = encrypted_path
        self.key_path = key_path
        self.prefer_keyring = prefer_keyring
        self.service_name = service_name

    def set(self, name: str, value: str) -> str:
        if self.prefer_keyring:
            try:
                import keyring

                keyring.set_password(self.service_name, name, value)
                return "keychain"
            except Exception:
                pass
        secrets = self._read_encrypted()
        secrets[name] = value
        self._write_encrypted(secrets)
        return "encrypted-file"

    def get(self, name: str) -> str | None:
        if self.prefer_keyring:
            try:
                import keyring

                value = keyring.get_password(self.service_name, name)
                if value:
                    return value
            except Exception:
                pass
        return self._read_encrypted().get(name)

    def _fernet(self) -> Fernet:
        self.key_path.parent.mkdir(parents=True, exist_ok=True)
        if not self.key_path.exists():
            self.key_path.write_bytes(Fernet.generate_key())
            os.chmod(self.key_path, 0o600)
        return Fernet(self.key_path.read_bytes())

    def _read_encrypted(self) -> dict[str, str]:
        if not self.encrypted_path.exists():
            return {}
        try:
            plaintext = self._fernet().decrypt(self.encrypted_path.read_bytes())
            payload = json.loads(plaintext.decode("utf-8"))
        except (InvalidToken, ValueError, json.JSONDecodeError):
            raise RuntimeError("Local provider secret store cannot be decrypted.")
        if not isinstance(payload, dict):
            raise RuntimeError("Local provider secret store has an invalid format.")
        return {
            str(key): str(value)
            for key, value in payload.items()
            if isinstance(key, str) and isinstance(value, str)
        }

    def _write_encrypted(self, payload: dict[str, str]) -> None:
        self.encrypted_path.parent.mkdir(parents=True, exist_ok=True)
        ciphertext = self._fernet().encrypt(
            json.dumps(payload, ensure_ascii=False, sort_keys=True).encode("utf-8")
        )
        self.encrypted_path.write_bytes(ciphertext)
        os.chmod(self.encrypted_path, 0o600)
