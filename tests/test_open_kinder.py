"""유치원을 열어 드리는 자리.

가입 신청 → 승인을 거치지 않고 우리가 먼저 자리를 깔아 드리는 경우가 있다.
시범 운영이 그렇다. 그때 빠뜨리면 안 되는 것이 셋이다.

    - 들어가자마자 빈 화면을 마주하지 않을 것 (반·차수가 채워져 있을 것)
    - 원아는 없을 것 — 명부를 올리는 것이 그 원의 첫 일이다
    - **처음 비밀번호는 첫 로그인 때 본인이 다시 정할 것**
      우리가 정해 건넨 값은 이미 남의 손(카톡·문자)을 거쳤다
"""

from __future__ import annotations

import pytest
from sqlalchemy import create_engine, func, select
from sqlalchemy.orm import sessionmaker

from firstout.models import (
    ROLE_ADMIN,
    ROLE_OPERATOR,
    Base,
    Child,
    ClassRoom,
    Kindergarten,
    Round,
    User,
)
from firstout.security import verify_password
from firstout.seed import open_kinder, seed_operator


@pytest.fixture()
def db():
    engine = create_engine("sqlite://")
    Base.metadata.create_all(engine)
    s = sessionmaker(bind=engine)()
    yield s
    s.close()


def test_유치원과_총괄_관리자가_함께_생긴다(db):
    got = open_kinder(db, "주덕화곡초등학교 병설유치원", "지민희", "jimin", "1234")
    assert got is not None
    k, u = got

    assert k.name == "주덕화곡초등학교 병설유치원"
    assert k.usable, "바로 쓸 수 있는 상태여야 한다"
    assert u.name == "지민희"
    assert u.login_id == "jimin"
    assert u.role == ROLE_ADMIN
    assert u.kinder_id == k.id


def test_처음_비밀번호는_첫_로그인_때_다시_정한다(db):
    _, u = open_kinder(db, "봄뜰유치원", "지민희", "jimin", "1234")
    assert verify_password("1234", u.password_hash), "건넨 값으로 들어올 수는 있어야 한다"
    assert u.must_change_pw, "그 값 그대로 계속 쓰게 두면 안 된다"


def test_운영자도_첫_로그인_때_다시_정한다(db):
    u = seed_operator(db, "admin", "1234")
    assert u is not None
    assert u.role == ROLE_OPERATOR
    assert u.must_change_pw


def test_들어가자마자_빈_화면을_마주하지_않는다(db):
    k, _ = open_kinder(db, "봄뜰유치원", "지민희", "jimin", "1234")
    반 = db.scalar(select(func.count(ClassRoom.id)).where(ClassRoom.kinder_id == k.id))
    차수 = db.scalar(select(func.count(Round.id)).where(Round.kinder_id == k.id))
    assert 반 > 0 and 차수 > 0, "반과 귀가 차수가 미리 채워져 있어야 한다"


def test_원아는_넣지_않는다(db):
    k, _ = open_kinder(db, "봄뜰유치원", "지민희", "jimin", "1234")
    아이 = db.scalar(select(func.count(Child.id)).where(Child.kinder_id == k.id))
    assert 아이 == 0, "명부를 올리는 것이 그 원의 첫 일이다"


def test_같은_이름이나_같은_아이디면_아무것도_안_한다(db):
    open_kinder(db, "봄뜰유치원", "지민희", "jimin", "1234")

    assert open_kinder(db, "봄뜰유치원", "다른사람", "other", "1234") is None
    assert open_kinder(db, "다른유치원", "지민희", "jimin", "1234") is None

    assert db.scalar(select(func.count(Kindergarten.id))) == 1
    assert db.scalar(select(func.count(User.id))) == 1
