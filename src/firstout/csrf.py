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

        status = {"code": 0, "set": []}

        async def watch(message):
            if message["type"] == "http.response.start":
                status["code"] = message["status"]
                # 로그인·초대처럼 **이 응답에서 처음 로그인되는** 경우가 있다.
                # 요청 쿠키만 보면 그런 기록이 모두 「누구인지 모름」으로 남아,
                # 정작 중요한 "누가 로그인했나" 가 유치원 감사 로그에서 빠진다.
                status["set"] = [
                    v.decode("latin-1")
                    for k, v in message.get("headers", [])
                    if k.lower() == b"set-cookie"
                ]
            await send(message)

        try:
            await self.app(scope, receive, watch)
        finally:
            self._record(scope, path, status["code"], status["set"])

    def _record(self, scope, path: str, status: int, set_cookies: list[str]) -> None:
        import time

        from . import audit
        from .db import SessionLocal

        try:
            with SessionLocal() as db:
                cookie = _cookie_named(scope, "majung") or _set_cookie_named(set_cookies, "majung")
                audit.write(
                    db,
                    user=audit.user_from_cookie(db, cookie),
                    method=scope.get("method", ""),
                    path=path,
                    status=status,
                    ip=client_ip(scope),
                    agent=_header(scope, b"user-agent"),
                )
                # 한 시간에 한 번만 뒷정리를 한다 — 매 요청마다 훑을 일이 아니다.
                # 유치원은 서버를 몇 달씩 켜 두므로 시작할 때만 해서는 안 된다.
                if time.time() - self._last_purge > 3600:
                    self._last_purge = time.time()
                    from . import backup, invites, retention

                    audit.purge_old(db)
                    retention.purge_signatures(db)
                    invites.sweep(db)
                    backup.run()          # 오늘 사본이 이미 있으면 아무것도 하지 않는다
        except Exception:   # noqa: BLE001 — 기록 실패가 서비스를 멈추면 안 된다
            pass


def _set_cookie_named(set_cookies: list[str], want: str) -> str | None:
    """응답에서 새로 심는 쿠키 — 방금 로그인한 사람을 알아내는 데 쓴다."""
    for raw in set_cookies:
        k, _, v = raw.split(";")[0].strip().partition("=")
        if k == want and v:
            return v
    return None


def _cookie_named(scope, want: str) -> str | None:
    for name, value in scope.get("headers", []):
        if name == b"cookie":
            for part in value.decode("latin-1").split(";"):
                k, _, v = part.strip().partition("=")
                if k == want:
                    return v
    return None


def client_ip(scope) -> str:
    """프록시 뒤에서는 진짜 접속지가 헤더에 담겨 온다.

    감사 로그와 속도 제한이 **같은 값**을 봐야 셈이 맞으므로 여기 한 곳에서만 정한다.
    """
    fwd = _header(scope, b"x-forwarded-for")
    if fwd:
        return fwd.split(",")[0].strip()
    client = scope.get("client")
    return client[0] if client else ""


# ── 브라우저에게 지켜달라고 알리는 것들 ─────────────────

# 우리 화면은 바깥 자원을 하나도 쓰지 않는다 (글꼴·스크립트를 모두 서버에 담았다).
# 그래서 「우리 서버 것만 쓰라」고 못박을 수 있다. 혹시 어딘가로 남의 스크립트가
# 끼어들어도 브라우저가 실행하지 않는다.
#
# img 에 data: 를 여는 것은 인계 서명이 data:image/png 이기 때문이고,
# style 에 unsafe-inline 을 두는 것은 화면 곳곳의 style="…" 때문이다.
# 스크립트에는 열어주지 않는다 — 그쪽이 위험한 쪽이다.
_CSP = (
    "default-src 'self'; base-uri 'self'; form-action 'self'; frame-ancestors 'none'; "
    "img-src 'self' data:; style-src 'self' 'unsafe-inline'; font-src 'self'; "
    "connect-src 'self'; object-src 'none'; script-src 'self' 'nonce-{nonce}'"
)

_FIXED = [
    ("X-Content-Type-Options", "nosniff"),
    # 다른 사이트가 우리 화면을 창 안에 숨겨 띄우고 「귀가 처리」를 누르게 할 수 없도록
    ("X-Frame-Options", "DENY"),
    # 주소에 아이 번호가 실리므로 바깥으로 흘리지 않는다
    ("Referrer-Policy", "same-origin"),
    ("Permissions-Policy", "geolocation=(), microphone=(), camera=(), payment=()"),
    ("Cross-Origin-Opener-Policy", "same-origin"),
]

HSTS = "max-age=31536000; includeSubDomains"


class SecurityHeaders:
    """모든 응답에 같은 규칙을 붙인다.

    화면마다 챙기면 언젠가 빠뜨린다. 여기 한 곳에서만 정한다.
    """

    def __init__(self, app):
        self.app = app

    async def __call__(self, scope, receive, send):
        if scope["type"] != "http":
            return await self.app(scope, receive, send)

        import secrets

        nonce = secrets.token_urlsafe(12)
        scope.setdefault("state", {})["csp_nonce"] = nonce
        https = _is_https(scope)

        async def go(message):
            if message["type"] == "http.response.start":
                head = message.setdefault("headers", [])
                pairs = [("Content-Security-Policy", _CSP.format(nonce=nonce)), *_FIXED]
                if https:
                    pairs.append(("Strict-Transport-Security", HSTS))
                head.extend((k.encode("latin-1"), v.encode("latin-1")) for k, v in pairs)
            await send(message)

        await self.app(scope, receive, go)


def _is_https(scope) -> bool:
    fwd = _header(scope, b"x-forwarded-proto")
    return scope.get("scheme") == "https" or fwd.split(",")[0].strip() == "https"


# ── 첫 비밀번호는 반드시 바꾸게 한다 ────────────────────

# 이 길들은 막지 않는다 — 막으면 비밀번호를 바꾸러 갈 수조차 없다
_PW_FREE = ("/me/password", "/signin", "/signout", "/signup", "/join/", "/static/",
            "/sw.js", "/health", "/favicon.ico", "/connect")


class ForcePasswordChange:
    """임시 비밀번호로는 첫 화면 말고 아무 데도 못 가게 한다.

    지금까지는 첫 화면에서만 비밀번호 변경으로 보냈다. 그래서 주소를 직접 치면
    그냥 지나갈 수 있었고, **카카오톡으로 오간 임시 비밀번호가 계속 살아 있었다.**
    바꾸기 전까지는 어느 문도 열리지 않아야 한다.
    """

    def __init__(self, app):
        self.app = app

    async def __call__(self, scope, receive, send):
        path = scope.get("path", "")
        if scope["type"] != "http" or path.startswith(_PW_FREE):
            return await self.app(scope, receive, send)

        from . import audit
        from .db import SessionLocal

        try:
            with SessionLocal() as db:
                me = audit.user_from_cookie(db, _cookie_named(scope, "majung"))
                must = bool(me and me.must_change_pw)
        except Exception:   # noqa: BLE001 — 확인에 실패했다고 서비스를 멈추지 않는다
            must = False

        if must:
            res = RedirectResponse("/me/password", status_code=303)
            return await res(scope, receive, send)
        return await self.app(scope, receive, send)
