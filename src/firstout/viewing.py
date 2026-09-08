"""운영자가 유치원 화면을 둘러본다.

「지금 그 원이 어떤 상태인가」를 알려면 매번 계정을 물어봐야 했다. 그건 원에도
번거롭고 우리에게도 느리다. 그래서 운영 화면에서 유치원을 눌러 그대로 들어가 본다.

**보기만 한다.** 남의 원 자료를 우리가 고칠 수 있으면 안 된다 —
누가 고쳤는지 알 수 없어지고, 무엇보다 그럴 이유가 없다. 상태를 보는 것이 목적이다.
바꾸는 요청은 미들웨어(csrf.ViewOnly)가 막는다.

둘러보는 동안에는 화면 맨 위에 그 사실이 계속 떠 있다. 어느 원을 보고 있는지 모른 채
이야기하면 사고가 난다. 두 시간이 지나면 저절로 풀린다.
"""

from __future__ import annotations

from itsdangerous import BadSignature, URLSafeTimedSerializer
from starlette.responses import Response

from .config import SECRET_KEY

COOKIE = "majung_view"
MAX_AGE = 2 * 60 * 60      # 두 시간이면 통화 한 번에는 넉넉하다

# 둘러보는 중에도 눌러야 하는 길 — 나가기와 로그아웃, 그리고 운영 화면
FREE = ("/operator", "/view/stop", "/signout", "/reauth", "/me/password")

_ser = URLSafeTimedSerializer(SECRET_KEY, salt="majung-view")


def start(res: Response, kinder_id: int, secure: bool) -> Response:
    res.set_cookie(
        COOKIE, _ser.dumps({"k": int(kinder_id)}),
        max_age=MAX_AGE, httponly=True, samesite="lax", secure=secure,
    )
    return res


def stop(res: Response) -> Response:
    res.delete_cookie(COOKIE)
    return res


def which(raw: str | None) -> int | None:
    """둘러보는 중인 유치원 번호. 아니면 None."""
    if not raw:
        return None
    try:
        return int(_ser.loads(raw, max_age=MAX_AGE)["k"])
    except (BadSignature, KeyError, ValueError, TypeError):
        return None


def blocked(path: str) -> bool:
    """둘러보는 중에 막아야 하는 길인가."""
    return not path.startswith(FREE)
