from app.secret_store import SecretStore


def test_encrypted_secret_fallback_never_writes_plaintext(tmp_path) -> None:
    store = SecretStore(
        encrypted_path=tmp_path / "secrets.enc",
        key_path=tmp_path / "secrets.key",
        prefer_keyring=False,
    )

    backend = store.set("PROVIDER_KEY", "top-secret-value")

    assert backend == "encrypted-file"
    assert store.get("PROVIDER_KEY") == "top-secret-value"
    assert b"top-secret-value" not in (tmp_path / "secrets.enc").read_bytes()
