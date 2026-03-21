from cryptography.hazmat.primitives.asymmetric.ed25519 import (
    Ed25519PrivateKey, Ed25519PublicKey
)
from cryptography.hazmat.primitives import serialization
from pathlib import Path
import base64, json

KEY_DIR = Path.home() / ".agentwit"
PRIVATE_KEY_PATH = KEY_DIR / "signing_key.pem"
PUBLIC_KEY_PATH  = KEY_DIR / "signing_pub.pem"

class EventSigner:
    def __init__(self):
        KEY_DIR.mkdir(exist_ok=True)
        if not PRIVATE_KEY_PATH.exists():
            self._generate_keypair()
        self._private_key = self._load_private_key()
        self._public_key  = self._private_key.public_key()

    def _generate_keypair(self):
        key = Ed25519PrivateKey.generate()
        # 秘密鍵保存
        with open(PRIVATE_KEY_PATH, "wb") as f:
            f.write(key.private_bytes(
                serialization.Encoding.PEM,
                serialization.PrivateFormat.PKCS8,
                serialization.NoEncryption()
            ))
        PRIVATE_KEY_PATH.chmod(0o600)
        # 公開鍵保存
        with open(PUBLIC_KEY_PATH, "wb") as f:
            f.write(key.public_key().public_bytes(
                serialization.Encoding.PEM,
                serialization.PublicFormat.SubjectPublicKeyInfo
            ))

    def _load_private_key(self) -> Ed25519PrivateKey:
        with open(PRIVATE_KEY_PATH, "rb") as f:
            return serialization.load_pem_private_key(f.read(), password=None)

    def sign(self, event: dict) -> str:
        """イベントをJSON化して署名。base64文字列を返す"""
        data = json.dumps(event, sort_keys=True, ensure_ascii=False).encode()
        sig  = self._private_key.sign(data)
        return base64.b64encode(sig).decode()

    def verify(self, event: dict, signature: str) -> bool:
        """署名を検証。Trueなら正常"""
        try:
            data = json.dumps(event, sort_keys=True, ensure_ascii=False).encode()
            self._public_key.verify(base64.b64decode(signature), data)
            return True
        except Exception:
            return False

    def fingerprint(self) -> str:
        """公開鍵のfingerprint（先頭16文字）"""
        pub = self._public_key.public_bytes(
            serialization.Encoding.Raw,
            serialization.PublicFormat.Raw
        )
        import hashlib
        return hashlib.sha256(pub).hexdigest()[:16]
