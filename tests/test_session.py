"""로그인 유지 기간과 민감 화면 재확인.

개인 휴대폰은 길게, 공용 태블릿은 짧게 — 쿠키 만료는 브라우저가 지키는 값이라
훔쳐간 쪽에는 의미가 없다. 서버가 스스로 끊는지를 시험한다.
"""

from __future__ import annotations

from firstout import audit, reauth
from firstout.security import (
    SESSION_PERSONAL,
    SESSION_SHARED,
    hash_password,
    make_token,
    pw_stamp,
    read_token,
)


class _When:
    """토큰을 만든 시각을 뒤로 돌려 「시간이 지난 뒤」를 흉내 낸다."""

    def __init__(self, seconds: float):
        self.seconds = seconds

    def __enter__(self):
        import itsdangerous.timed as t

        self.real = t.time.time
        t.time.time = lambda: self.real() - self.seconds
        return self

    def __exit__(self, *a):
        import itsdangerous.timed as t

        t.time.time = self.real


def test_공용_기기는_열두시간_뒤_끊긴다():
    stored = hash_password("majung1234")
    with _When(SESSION_SHARED - 60):
        fresh = make_token(7, stored, SESSION_SHARED)
    with _When(SESSION_SHARED + 60):
        stale = make_token(7, stored, SESSION_SHARED)

    assert read_token(fresh) == (7, pw_stamp(stored))
    assert read_token(stale) is None


def test_개인_휴대폰은_육십일_동안_유지된다():
    stored = hash_password("majung1234")
    with _When(SESSION_SHARED + 3600):        # 공용이었다면 이미 끊겼을 시점
        t = make_token(7, stored, SESSION_PERSONAL)
    assert read_token(t) == (7, pw_stamp(stored))


def test_기간을_늘려_적어도_한계를_넘지_못한다():
    """토큰 안의 값이 바뀌어도 서명이 깨지지만, 한계 자체도 서버가 잡는다."""
    stored = hash_password("majung1234")
    with _When(SESSION_PERSONAL + 3600):
        t = make_token(7, stored, SESSION_PERSONAL * 10)
    assert read_token(t) is None


def test_비밀번호를_바꾸면_모든_기기가_끊긴다():
    old = hash_password("majung1234")
    t = make_token(7, old, SESSION_PERSONAL)
    new = hash_password("majung5678")
    assert read_token(t)[1] != pw_stamp(new)


# ── 민감 화면 재확인 ────────────────────────────────────

def test_돌아갈_곳은_우리_화면이어야_한다():
    """확인만 시켜놓고 남의 사이트로 보내는 수법을 막는다."""
    assert reauth.safe_next("/users") == "/users"
    assert reauth.safe_next("/roster/export?cls=3") == "/roster/export?cls=3"
    assert reauth.safe_next("//evil.example") == "/"
    assert reauth.safe_next("https://evil.example") == "/"
    assert reauth.safe_next(r"/\evil") == "/"
    assert reauth.safe_next("") == "/"


class _Fake:
    def __init__(self, cookies=None, method="GET"):
        self.cookies = cookies or {}
        self.method = method


class _User:
    id = 7
    password_hash = hash_password("majung1234")


def test_확인하면_통과하고_비밀번호를_바꾸면_풀린다():
    from starlette.responses import RedirectResponse

    u = _User()
    res = reauth.grant(RedirectResponse("/users"), u, secure=False)
    raw = res.headers["set-cookie"].split(";")[0].split("=", 1)[1]

    assert reauth.ok(_Fake({reauth.COOKIE: raw}), u)
    assert not reauth.ok(_Fake({}), u)

    u2 = _User()
    u2.password_hash = hash_password("majung5678")
    assert not reauth.ok(_Fake({reauth.COOKIE: raw}), u2)


def test_확인_전에는_확인_화면으로_보낸다():
    u = _User()
    got = reauth.wall(_Fake({}, method="POST"), u, back="/users")
    assert got is not None
    assert "/reauth?next=%2Fusers" in got.headers["location"]


# ── 감사 로그 ───────────────────────────────────────────

def test_초대_주소는_기록에_원문이_남지_않는다():
    """감사 로그는 한 달을 산다. 그 안에 열쇠가 굴러다니면 안 된다."""
    assert audit.mask("/join/AbCdEf-1234_xyz") == "/join/…"
    assert audit.mask("/board") == "/board"
    assert audit.describe("/join/AbCdEf") == "초대로 첫 로그인"
