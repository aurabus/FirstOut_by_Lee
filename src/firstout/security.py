"""비밀번호·세션·CSRF.

인터넷에 공개된 서버라 원내망 때와 기준이 다르다.
아이를 데려갈 권한이 걸린 시스템이므로 로그인을 뚫리게 두면 안 된다.
"""

from __future__ import annotations

import hashlib
import hmac
import secrets

from itsdangerous import BadSignature, URLSafeTimedSerializer

from .config import SECRET_KEY

_ITER = 240_000


# ── 비밀번호 ────────────────────────────────────────────

def hash_password(password: str) -> str:
    """계정마다 다른 소금을 쓴다. 같은 비밀번호라도 저장값이 달라야
    한 계정이 뚫렸을 때 나머지가 함께 뚫리지 않는다."""
    salt = secrets.token_hex(16)
    digest = hashlib.pbkdf2_hmac("sha256", password.encode(), salt.encode(), _ITER).hex()
    return f"pbkdf2${_ITER}${salt}${digest}"


def verify_password(password: str, stored: str) -> bool:
    if not stored or stored.count("$") != 3:
        return False
    _, iters, salt, digest = stored.split("$")
    try:
        calc = hashlib.pbkdf2_hmac("sha256", password.encode(), salt.encode(), int(iters)).hex()
    except ValueError:
        return False
    return hmac.compare_digest(calc, digest)


def password_problem(password: str) -> str:
    """지키기 힘든 규칙을 만들면 메모지에 적어 모니터에 붙인다.
    길이만 확보하고 나머지는 강요하지 않는다."""
    if len(password) < 8:
        return "비밀번호는 8자 이상으로 정해주세요"
    if password.isdigit():
        return "숫자만으로는 안 됩니다 — 글자를 섞어주세요"
    if password.lower() in {"password", "12345678", "qwertyui", "majung12"}:
        return "너무 흔한 비밀번호입니다"
    return ""


# ── 로그인 세션 ─────────────────────────────────────────

_session = URLSafeTimedSerializer(SECRET_KEY, salt="majung-session")
SESSION_MAX_AGE = 60 * 60 * 24 * 14   # 2주 — 하원 때마다 다시 로그인하지 않도록


def pw_stamp(password_hash: str) -> str:
    """비밀번호가 바뀌면 달라지는 짧은 표식."""
    return hashlib.sha256(password_hash.encode()).hexdigest()[:12]


def make_token(user_id: int, password_hash: str = "") -> str:
    return _session.dumps({"u": user_id, "p": pw_stamp(password_hash)})


def read_token(token: str | None, max_age: int = SESSION_MAX_AGE) -> tuple[int, str] | None:
    """(계정 id, 비밀번호 표식) 을 돌려준다.

    표식을 함께 담아두면, 비밀번호를 바꾸는 순간 다른 기기에 남아 있던
    로그인이 모두 끊긴다. 비밀번호가 샜을 때 되찾는 유일한 방법이다.
    """
    if not token:
        return None
    try:
        data = _session.loads(token, max_age=max_age)
        return int(data["u"]), str(data.get("p", ""))
    except (BadSignature, KeyError, ValueError, TypeError):
        return None


# ── CSRF ────────────────────────────────────────────────
# 공개 서버에서는 다른 사이트가 우리 화면의 POST 를 대신 보내게 만들 수 있다.
# 아이를 "귀가 처리" 하는 요청이 그렇게 들어오면 안 되므로 토큰으로 막는다.

CSRF_COOKIE = "majung_csrf"
CSRF_FIELD = "_csrf"


def new_csrf() -> str:
    return secrets.token_urlsafe(24)


def csrf_ok(cookie: str | None, sent: str | None) -> bool:
    """보낸 값은 아무 문자열이나 올 수 있으므로 바이트로 비교한다.

    문자열끼리 비교하면 한글 같은 비ASCII 값이 들어왔을 때 예외가 나서,
    막아야 할 요청이 오히려 500 오류가 된다.
    """
    if not cookie or not sent:
        return False
    return hmac.compare_digest(str(cookie).encode("utf-8"), str(sent).encode("utf-8"))
