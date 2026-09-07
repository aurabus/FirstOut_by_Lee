"""화면에 한 번만 보여줄 안내문.

처리 결과를 `?msg=김민준 귀가 처리` 처럼 주소에 실어 보내면
**원아 이름이 브라우저 기록과 서버 접속 로그에 그대로 남는다.**
임시 비밀번호도 마찬가지다. 그래서 짧게 살아 있는 쿠키로 옮긴다.
"""

from __future__ import annotations

from itsdangerous import BadSignature, URLSafeTimedSerializer
from starlette.responses import Response

from .config import PUBLIC_URL, SECRET_KEY

COOKIE = "majung_flash"
MAX_AGE = 60   # 곧바로 다음 화면에서 쓰고 버린다

# 이 쿠키에는 임시 비밀번호와 초대 토큰이 담긴다. HTTPS 로 서비스하는 중이라면
# 반드시 Secure 를 걸어야 한다 — 걸지 않으면 평문 요청 한 번으로 새어 나간다.
# 요청마다 판단하는 세션 쿠키와 달리 여기는 request 가 없으므로 설정을 본다.
SECURE = PUBLIC_URL.startswith("https://")

_ser = URLSafeTimedSerializer(SECRET_KEY, salt="majung-flash")


def put(res: Response, msg: str = "", secret: str = "") -> Response:
    """다음 화면에 보여줄 문구를 담는다. secret 은 임시 비밀번호처럼 한 번만 보여줄 값."""
    if not msg and not secret:
        return res
    res.set_cookie(
        COOKIE,
        _ser.dumps({"m": msg, "s": secret}),
        max_age=MAX_AGE,
        httponly=True,
        samesite="lax",
        secure=SECURE,
    )
    return res


def take(request) -> tuple[str, str]:
    """읽고 나면 지운다. 새로고침해도 같은 안내가 반복되지 않는다."""
    raw = request.cookies.get(COOKIE)
    if not raw:
        return "", ""
    try:
        data = _ser.loads(raw, max_age=MAX_AGE)
    except (BadSignature, ValueError, TypeError):
        return "", ""
    return data.get("m", ""), data.get("s", "")


def clear(res: Response) -> Response:
    res.delete_cookie(COOKIE)
    return res
