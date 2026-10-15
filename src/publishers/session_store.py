"""note セッションをリポジトリ内に暗号化して保存・読み込みする

GitHub Actions の GITHUB_TOKEN では Secret を書き換えられないため、
延長されたセッションは SESSION_KEY（Secret）で暗号化して data/session/ にコミットする。
これにより Personal Access Token もパスワードログインも不要になる
（note のログイン画面には reCAPTCHA があり、Actions からの自動ログインはできない）。
"""

import base64
import json
import os
from pathlib import Path

from nacl import secret, utils

ROOT = Path(__file__).resolve().parent.parent.parent
ENCRYPTED_FILE = ROOT / "data" / "session" / "note_session.enc"


def generate_key() -> str:
    return base64.b64encode(utils.random(secret.SecretBox.KEY_SIZE)).decode()


def _box(key_b64=None):
    key_b64 = key_b64 or os.environ.get("SESSION_KEY")
    if not key_b64:
        return None
    return secret.SecretBox(base64.b64decode(key_b64))


def save_encrypted(state: dict, key_b64=None, path=ENCRYPTED_FILE) -> bool:
    box = _box(key_b64)
    if box is None:
        return False
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(base64.b64encode(box.encrypt(json.dumps(state).encode("utf-8"))))
    return True


def load_encrypted(key_b64=None, path=ENCRYPTED_FILE):
    box = _box(key_b64)
    if box is None or not path.exists():
        return None
    return json.loads(box.decrypt(base64.b64decode(path.read_bytes())).decode("utf-8"))
