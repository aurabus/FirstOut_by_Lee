"""계정과 권한 검증.

공개 서버라 로그인이 뚫리면 아이를 데려갈 권한이 통째로 넘어간다.
비밀번호 저장 방식과 역할 구분을 시험으로 묶어 둔다.
"""

from __future__ import annotations

from firstout.models import ROLE_ADMIN, ROLE_OPERATOR, ROLE_TEACHER, Guardian, User
from firstout.security import (
    csrf_ok,
    hash_password,
    make_token,
    new_csrf,
    password_problem,
    pw_stamp,
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
    stored = hash_password("majung1234")
    t = make_token(7, stored)
    assert read_token(t) == (7, pw_stamp(stored))
    # 마지막 글자 하나만 바꿔도 무효. 원래 글자와 반드시 다른 값을 넣는다
    # (「xx 로 바꾼다」로 두면 토큰이 우연히 xx 로 끝나는 날 시험이 통과해 버린다)
    other = "a" if t[-1] != "a" else "b"
    assert read_token(t[:-1] + other) is None
    assert read_token(None) is None


def test_csrf_는_같은_값일_때만_통과한다():
    t = new_csrf()
    assert csrf_ok(t, t)
    assert not csrf_ok(t, "다른값")
    assert not csrf_ok(None, t)
    assert not csrf_ok(t, None)


def test_역할에_따라_권한이_갈린다():
    op = User(login_id="op", name="운영자", role=ROLE_OPERATOR)
    owner = User(login_id="w", name="원장", role=ROLE_ADMIN, kinder_id=1)
    teacher = User(login_id="t", name="교사", role=ROLE_TEACHER, kinder_id=1)

    assert op.is_operator and op.is_admin
    assert owner.is_admin and not owner.is_operator
    assert not teacher.is_admin and not teacher.is_operator


# ── 세션 무효화 ─────────────────────────────────────────

def test_비밀번호를_바꾸면_예전_세션이_끊긴다():
    """비밀번호가 샜을 때 되찾는 유일한 방법이다."""
    old = hash_password("majung1234")
    token = make_token(7, old)
    assert read_token(token) == (7, pw_stamp(old))

    new = hash_password("majung5678")
    uid, stamp = read_token(token)
    assert uid == 7
    assert stamp != pw_stamp(new)   # 예전 토큰의 표식이 더는 맞지 않는다


def test_표식이_없는_옛_토큰은_통하지_않는다():
    """예전 방식으로 만들어진 토큰은 비밀번호 표식이 맞지 않아 거부된다."""
    stored = hash_password("majung1234")
    _, stamp = read_token(make_token(7))     # 비밀번호를 넣지 않고 만든 토큰
    assert stamp != pw_stamp(stored)


# ── 개인정보 가리기 ─────────────────────────────────────

def test_연락처는_가운데를_가려서_보여준다():
    """저장은 하되 화면에는 옮겨 적을 수 없게 나와야 한다."""
    for raw, want in [
        ("010-1234-5678", "010-****-5678"),
        ("01012345678", "010-****-5678"),
        ("02-123-4567", "02-***-4567"),
        ("", ""),
    ]:
        g = Guardian(name="박영희", phone=raw)
        assert g.phone_masked == want
        if raw:
            assert raw.replace("-", "") not in g.phone_masked


def test_연락처_유무를_구분한다():
    assert Guardian(name="x", phone="010-1234-5678").has_phone
    assert not Guardian(name="x", phone="").has_phone
    assert not Guardian(name="x", phone="   ").has_phone
