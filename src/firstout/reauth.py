"""민감한 문 앞에서만 비밀번호를 다시 묻는다.

로그인은 길게 유지한다 — 귀가 중에 다시 로그인하라고 하면 아이 앞에서 손이 묶인다.
대신 **위험한 문 몇 개만** 잠근다.

    선생님 계정 관리 · 명부 엑셀 내려받기 · 감사 로그

휴대폰을 잠깐 놓고 자리를 비운 사이에 누가 명부를 통째로 내려받는 일을 막는 장치다.
귀가 처리는 절대 막지 않는다.
"""

from __future__ import annotations

import datetime as dt

from itsdangerous import BadSignature, URLSafeTimedSerializer
from starlette.responses import RedirectResponse, Response

from .config import SECRET_KEY
from .security import pw_stamp

COOKIE = "majung_su"
MAX_AGE = 10 * 60      # 한 번 확인하면 10분 동안은 묻지 않는다

_ser = URLSafeTimedSerializer(SECRET_KEY, salt="majung-reauth")


def grant(res: Response, user, secure: bool) -> Response:
    """확인됨을 표시한다. 비밀번호를 바꾸면 이 표시도 함께 무효가 된다."""
    res.set_cookie(
        COOKIE,
        _ser.dumps({"u": user.id, "p": pw_stamp(user.password_hash)}),
        max_age=MAX_AGE,
        httponly=True,
        samesite="lax",
        secure=secure,
    )
    return res


def ok(request, user) -> bool:
    raw = request.cookies.get(COOKIE)
    if not raw or user is None:
        return False
    try:
        data = _ser.loads(raw, max_age=MAX_AGE)
    except (BadSignature, ValueError, TypeError):
        return False
    return data.get("u") == user.id and data.get("p") == pw_stamp(user.password_hash)


def safe_next(path: str, fallback: str = "/") -> str:
    """돌아갈 곳은 우리 화면이어야 한다.

    확인만 시켜놓고 남의 사이트로 보내버리는 수법을 막는다.
    """
    if not path.startswith("/") or path.startswith("//") or "\\" in path:
        return fallback
    return path


def wall(request, user, back: str = "/") -> RedirectResponse | None:
    """확인이 필요하면 확인 화면으로 보낸다. 필요 없으면 None.

    확인이 끝나면 보던 화면으로 돌려보낸다. 다만 POST 처리 도중에 확인 시간이
    지났다면 그 주소로 되돌아갈 수 없으므로(그 길은 GET 을 받지 않는다),
    한 단계 위 화면으로 보낸다.
    """
    if ok(request, user):
        return None
    from urllib.parse import quote

    if request.method == "GET":
        q = f"?{request.url.query}" if request.url.query else ""
        want = safe_next(request.url.path + q)
    else:
        want = safe_next(back)
    return RedirectResponse(f"/reauth?next={quote(want, safe='')}", status_code=303)


def clear(res: Response) -> Response:
    res.delete_cookie(COOKIE)
    return res


def left(request, user) -> int:
    """남은 시간(초) — 화면에 보여주려고 쓴다."""
    raw = request.cookies.get(COOKIE)
    if not raw or not ok(request, user):
        return 0
    try:
        _, made = _ser.loads(raw, max_age=MAX_AGE, return_timestamp=True)
    except (BadSignature, ValueError, TypeError):
        return 0
    used = (dt.datetime.now(dt.timezone.utc) - made).total_seconds()
    return max(0, int(MAX_AGE - used))
