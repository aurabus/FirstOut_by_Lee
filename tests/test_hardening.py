"""취약점 점검에서 고친 것들이 계속 막히는지.

한 번 고쳐도 나중에 조용히 풀리는 것이 이런 것들이라 시험으로 묶어 둔다.
"""

from __future__ import annotations

import re

import pytest

from firstout.csrf import _CSP, _FIXED, _PW_FREE
from firstout.web import clip
from firstout.web.lists import SIGNATURE

# ── 서명은 캔버스가 만든 값만 받는다 ────────────────────

@pytest.mark.parametrize("bad", [
    "data:image/svg+xml;base64,PHN2Zz48L3N2Zz4=",      # svg 는 그림처럼 보이지만 문서다
    "data:text/html;base64,PHNjcmlwdD4=",
    "data:image/png;base64,<script>alert(1)</script>",
    "data:image/png;base64,",                           # 빈 값
    "data:image/png,notbase64!!",
    "javascript:alert(1)",
    "",
    "  data:image/png;base64,aaaa",                     # 앞에 공백을 붙인 우회
])
def test_이상한_서명은_받지_않는다(bad):
    assert not SIGNATURE.fullmatch(bad)


def test_캔버스가_만든_서명은_받는다():
    real = ("data:image/png;base64,iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJ"
            "AAAADUlEQVR42mP8z8BQDwAEhQGAhKmMIQAAAABJRU5ErkJggg==")
    assert SIGNATURE.fullmatch(real)


# ── 길이 ────────────────────────────────────────────────

def test_긴_입력은_잘라서_저장한다():
    """모델에 String(20) 이라고 적어도 SQLite 는 강제하지 않는다."""
    assert clip("가" * 500, 20) == "가" * 20
    assert clip("  박영희  ", 40) == "박영희"
    assert clip("", 40) == ""


# ── 브라우저에게 알리는 것들 ────────────────────────────

def test_스크립트는_우리_것만_실행된다():
    """script-src 에 unsafe-inline 이 들어가면 CSP 를 두는 의미가 사라진다."""
    csp = _CSP.format(nonce="abc")
    script = re.search(r"script-src[^;]*", csp).group(0)
    assert "'nonce-abc'" in script
    assert "unsafe-inline" not in script
    assert "unsafe-eval" not in script


def test_창_안에_숨겨_띄울_수_없다():
    """다른 사이트가 우리 화면을 씌워놓고 「귀가 처리」를 누르게 하는 수법을 막는다."""
    assert "frame-ancestors 'none'" in _CSP
    assert ("X-Frame-Options", "DENY") in _FIXED


def test_서명_그림은_열어두되_바깥_자원은_막는다():
    assert "img-src 'self' data:" in _CSP      # 서명이 data:image/png 다
    assert "default-src 'self'" in _CSP
    assert "object-src 'none'" in _CSP


def test_주소가_바깥으로_새지_않는다():
    """주소에 아이 번호가 실린다."""
    assert ("Referrer-Policy", "same-origin") in _FIXED


# ── 첫 비밀번호 ─────────────────────────────────────────

def test_비밀번호를_바꾸러_갈_길은_열려_있다():
    """전부 막으면 바꾸러 갈 수조차 없어 아무도 못 들어온다."""
    for must_open in ("/me/password", "/signin", "/signout", "/static/", "/health"):
        assert must_open.startswith(_PW_FREE)


def test_일하는_화면은_막힌다():
    """임시 비밀번호는 카카오톡을 타고 다닌다. 바꾸기 전에는 어느 문도 열리면 안 된다."""
    for blocked in ("/board", "/attend", "/roster", "/list/i1", "/child/3",
                    "/users", "/settings", "/audit", "/upload"):
        assert not blocked.startswith(_PW_FREE)


# ── 안내 쿠키 ───────────────────────────────────────────

def test_안내_쿠키는_https_에서_secure_가_걸린다(monkeypatch):
    """이 쿠키에 임시 비밀번호와 초대 토큰이 담긴다."""
    import importlib

    import firstout.config as config
    import firstout.flash as flash

    monkeypatch.setattr(config, "PUBLIC_URL", "https://majung.aurabus.co.kr")
    importlib.reload(flash)
    assert flash.SECURE is True

    monkeypatch.setattr(config, "PUBLIC_URL", "")
    importlib.reload(flash)
    assert flash.SECURE is False


# ── 접속지를 꾸며낼 수 없는가 ───────────────────────────

class _Scope(dict):
    """ASGI scope 흉내."""

    def __init__(self, xff="", client="198.51.100.1"):
        super().__init__(
            type="http",
            client=(client, 12345),
            headers=[(b"x-forwarded-for", xff.encode())] if xff else [],
        )


def test_프록시가_없으면_보내온_주소를_믿지_않는다(monkeypatch):
    """X-Forwarded-For 는 아무나 보낼 수 있는 헤더다.

    첫 값을 믿으면 헤더 한 줄로 속도 제한을 넘고 감사 로그에 거짓 주소를 남길 수 있다.
    실제로 그렇게 여덟 번 연속 가입 신청이 통과했다.
    """
    import firstout.config as config
    from firstout.csrf import client_ip

    monkeypatch.setattr(config, "PROXY_HOPS", 0)
    assert client_ip(_Scope(xff="9.9.9.9")) == "198.51.100.1"
    assert client_ip(_Scope(xff="9.9.9.9, 8.8.8.8")) == "198.51.100.1"
    assert client_ip(_Scope()) == "198.51.100.1"


def test_프록시가_있으면_그것이_붙인_자리만_본다(monkeypatch):
    """프록시는 받은 값 뒤에 진짜 주소를 덧붙인다. 앞의 값은 손님이 꾸민 것이다."""
    import firstout.config as config
    from firstout.csrf import client_ip

    monkeypatch.setattr(config, "PROXY_HOPS", 1)
    assert client_ip(_Scope(xff="9.9.9.9, 203.0.113.7")) == "203.0.113.7"
    assert client_ip(_Scope(xff="203.0.113.7")) == "203.0.113.7"
    # 헤더가 아예 없으면 붙여준 사람이 없다는 뜻이라 접속한 자리를 쓴다
    assert client_ip(_Scope()) == "198.51.100.1"

    monkeypatch.setattr(config, "PROXY_HOPS", 2)
    assert client_ip(_Scope(xff="9.9.9.9, 203.0.113.7, 10.0.0.1")) == "203.0.113.7"


# ── 한 곳의 큰 파일이 모두를 멈추게 하지 않는가 ─────────

def test_아주_큰_명부는_읽지_않는다():
    """5MB 파일 하나에 13만 줄이 들어간다. 그걸 읽는 동안 다른 유치원이 멈춘다."""
    from firstout.excel import MAX_ROWS

    assert 500 <= MAX_ROWS <= 5000       # 제일 큰 유치원의 열 배쯤
