"""CSRF 검사.

공개 서버에서는 다른 사이트가 우리 화면의 POST 를 대신 보내게 만들 수 있다.
아이를 「귀가 처리」 하는 요청이 그렇게 들어오면 안 되므로 토큰으로 막는다.

FastAPI 의 일반 미들웨어로 만들면 본문을 먼저 읽어버려서 라우터에는 빈 폼이 간다.
그래서 ASGI 단계에서 직접 처리하고, 읽은 본문을 그대로 되돌려준다.
"""

from __future__ import annotations

import re
from urllib.parse import parse_qs

from starlette.responses import RedirectResponse

from .security import CSRF_COOKIE, CSRF_FIELD, csrf_ok

# 파일 업로드(multipart)에서 토큰 칸만 골라낸다
_MULTIPART = re.compile(
    rb'name="' + CSRF_FIELD.encode() + rb'"\r?\n\r?\n(.*?)\r?\n--', re.DOTALL
)

# 검사에서 빼는 경로 — 로그인 화면조차 못 열면 아무것도 못 한다
EXEMPT = ("/health",)


def _token_in_body(body: bytes, content_type: str) -> str | None:
    if "application/x-www-form-urlencoded" in content_type:
        got = parse_qs(body.decode("utf-8", "replace")).get(CSRF_FIELD)
        return got[0] if got else None
    if "multipart/form-data" in content_type:
        m = _MULTIPART.search(body)
        return m.group(1).decode("utf-8", "replace").strip() if m else None
    return None


def _cookie(scope) -> str | None:
    for name, value in scope.get("headers", []):
        if name == b"cookie":
            for part in value.decode("latin-1").split(";"):
                k, _, v = part.strip().partition("=")
                if k == CSRF_COOKIE:
                    return v
    return None


def _header(scope, key: bytes) -> str:
    for name, value in scope.get("headers", []):
        if name == key:
            return value.decode("latin-1")
    return ""


class CSRFMiddleware:
    def __init__(self, app):
        self.app = app

    async def __call__(self, scope, receive, send):
        if scope["type"] != "http" or scope.get("method") != "POST":
            return await self.app(scope, receive, send)
        if scope.get("path", "").startswith(EXEMPT):
            return await self.app(scope, receive, send)

        # 본문을 다 읽는다 — 뒤에서 그대로 되돌려줄 것이다
        body = b""
        more = True
        while more:
            msg = await receive()
            body += msg.get("body", b"")
            more = msg.get("more_body", False)

        sent = _token_in_body(body, _header(scope, b"content-type"))
        if not csrf_ok(_cookie(scope), sent):
            res = RedirectResponse(
                "/signin?error=요청이 만료되었습니다 — 화면을 새로 열고 다시 시도해 주세요",
                status_code=303,
            )
            return await res(scope, receive, send)

        done = False

        async def replay():
            """라우터가 본문을 다시 읽을 수 있게 한 번 더 흘려보낸다."""
            nonlocal done
            if not done:
                done = True
                return {"type": "http.request", "body": body, "more_body": False}
            return {"type": "http.disconnect"}

        await self.app(scope, replay, send)


# ── 감사 로그 ───────────────────────────────────────────

class AuditMiddleware:
    """모든 요청을 남긴다 — 화면을 연 것까지.

    응답이 끝난 뒤에 적으므로 처리 결과(상태 코드)까지 함께 남고,
    기록하다 실패해도 서비스는 멈추지 않는다.
    """

    def __init__(self, app):
        self.app = app
        self._last_purge = 0.0

    async def __call__(self, scope, receive, send):
        if scope["type"] != "http":
            return await self.app(scope, receive, send)

        path = scope.get("path", "")
        from . import audit

        if not audit.should_log(path):
            return await self.app(scope, receive, send)

        status = {"code": 0}

        async def watch(message):
            if message["type"] == "http.response.start":
                status["code"] = message["status"]
            await send(message)

        try:
            await self.app(scope, receive, watch)
        finally:
            self._record(scope, path, status["code"])

    def _record(self, scope, path: str, status: int) -> None:
        import time

        from . import audit
        from .db import SessionLocal

        try:
            with SessionLocal() as db:
                cookie = _cookie_named(scope, "majung")
                audit.write(
                    db,
                    user=audit.user_from_cookie(db, cookie),
                    method=scope.get("method", ""),
                    path=path,
                    status=status,
                    ip=_client_ip(scope),
                    agent=_header(scope, b"user-agent"),
                )
                # 한 시간에 한 번만 오래된 기록을 치운다 — 매 요청마다 훑을 일이 아니다
                if time.time() - self._last_purge > 3600:
                    self._last_purge = time.time()
                    audit.purge_old(db)
        except Exception:   # noqa: BLE001 — 기록 실패가 서비스를 멈추면 안 된다
            pass


def _cookie_named(scope, want: str) -> str | None:
    for name, value in scope.get("headers", []):
        if name == b"cookie":
            for part in value.decode("latin-1").split(";"):
                k, _, v = part.strip().partition("=")
                if k == want:
                    return v
    return None


def _client_ip(scope) -> str:
    """프록시 뒤에서는 진짜 접속지가 헤더에 담겨 온다."""
    fwd = _header(scope, b"x-forwarded-for")
    if fwd:
        return fwd.split(",")[0].strip()
    client = scope.get("client")
    return client[0] if client else ""
