from __future__ import annotations

import getpass
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

from cryptography.fernet import Fernet


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from virtual_cybercafe.token_store import encrypt_token  # noqa: E402


def main() -> None:
    print("Paste the long-lived Instagram token. It will not be shown or stored as plain text.")
    token = getpass.getpass("Instagram token: ").strip()
    if not token:
        raise SystemExit("Token cannot be empty")
    key = Fernet.generate_key().decode("utf-8")
    token_path = ROOT / "state" / "instagram_token.enc"
    encrypt_token(token, key, token_path)
    meta = {"last_refreshed_at": datetime.now(timezone.utc).isoformat(), "expires_in_seconds": 5_184_000}
    (ROOT / "state" / "token_meta.json").write_text(json.dumps(meta, indent=2) + "\n", encoding="utf-8")
    print("\nEncrypted token written to state/instagram_token.enc")
    print("Add this value as the GitHub Actions secret TOKEN_ENCRYPTION_KEY:")
    print(key)
    print("Never commit or share the key printed above.")


if __name__ == "__main__":
    main()

