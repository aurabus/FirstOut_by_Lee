"""계정과 권한 검증.

공개 서버라 로그인이 뚫리면 아이를 데려갈 권한이 통째로 넘어간다.
비밀번호 저장 방식과 역할 구분을 시험으로 묶어 둔다.
"""

from __future__ import annotations

from firstout.models import ROLE_OPERATOR, ROLE_OWNER, ROLE_TEACHER, User
from firstout.security import (
    csrf_ok,
    hash_password,
    make_token,
    new_csrf,
    password_problem,
    read_token,
    verify_password,
)


def test_같은_비밀번호도_저장값이_다르다():
    """한 계정이 뚫려도 나머지가 함께 뚫리면 안 된다."""
    a, b = hash_password("majung1234"), hash_password("majung1234")
    assert a != b
    assert verify_password("majung1234", a)
    assert verify_password("majung1234", b)


def test_비밀번호는_원문으로_남지_않는다():
    stored = hash_password("majung1234")
    assert "majung1234" not in stored
    assert stored.startswith("pbkdf2$")


def test_틀린_비밀번호는_통과하지_못한다():
    stored = hash_password("majung1234")
    assert not verify_password("majung123", stored)
    assert not verify_password("", stored)
    assert not verify_password("majung1234", "")
    assert not verify_password("majung1234", "망가진값")


def test_너무_약한_비밀번호는_막는다():
    assert password_problem("1234")          # 짧다
    assert password_problem("12345678")      # 숫자만
    assert password_problem("password")      # 흔하다
    assert password_problem("majung1234") == ""


def test_세션_토큰은_위조되지_않는다():
    t = make_token(7)
    assert read_token(t) == 7
    assert read_token(t[:-2] + "xx") is None
    assert read_token(None) is None


def test_csrf_는_같은_값일_때만_통과한다():
    t = new_csrf()
    assert csrf_ok(t, t)
    assert not csrf_ok(t, "다른값")
    assert not csrf_ok(None, t)
    assert not csrf_ok(t, None)


def test_역할에_따라_권한이_갈린다():
    op = User(login_id="op", name="운영자", role=ROLE_OPERATOR)
    owner = User(login_id="w", name="원장", role=ROLE_OWNER, kinder_id=1)
    teacher = User(login_id="t", name="교사", role=ROLE_TEACHER, kinder_id=1)

    assert op.is_operator and op.is_admin
    assert owner.is_admin and not owner.is_operator
    assert not teacher.is_admin and not teacher.is_operator
