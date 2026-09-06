"""PIN 처리와 로그인 세션.

PIN 은 그대로 저장하지 않는다. 파일이 유출돼도 PIN 을 알아낼 수 없어야 한다.
"""

from __future__ import annotations

import hashlib
import hmac

from itsdangerous import BadSignature, URLSafeSerializer

from .config import SECRET_KEY

_SALT = b"majung-pin"


def hash_pin(pin: str) -> str:
    return hashlib.pbkdf2_hmac("sha256", pin.encode(), _SALT, 120_000).hex()


def verify_pin(pin: str, stored: str) -> bool:
    if not stored:
        return False
    return hmac.compare_digest(hash_pin(pin), stored)


_ser = URLSafeSerializer(SECRET_KEY, salt="majung-session")


def make_token(teacher_id: int) -> str:
    return _ser.dumps({"t": teacher_id})


def read_token(token: str | None) -> int | None:
    if not token:
        return None
    try:
        return int(_ser.loads(token)["t"])
    except (BadSignature, KeyError, ValueError, TypeError):
        return None
