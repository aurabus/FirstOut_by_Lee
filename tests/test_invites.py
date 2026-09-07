"""1회용 초대 — 한 번만, 10분만, 한 사람만.

임시 비밀번호를 카카오톡으로 돌리는 대신 쓰는 길이다.
「한 번만 쓸 수 있다」가 지켜지지 않으면 이 방식을 쓸 이유가 없어진다.
"""

from __future__ import annotations

import datetime as dt

import pytest
from sqlalchemy import create_engine, select
from sqlalchemy.orm import sessionmaker

from firstout import invites
from firstout.models import Base, Invite, Kindergarten, User
from firstout.security import hash_password

NOW = dt.datetime(2026, 9, 7, 15, 40)
KID = 1


@pytest.fixture()
def db():
    engine = create_engine("sqlite://")
    Base.metadata.create_all(engine)
    s = sessionmaker(bind=engine)()
    s.add(Kindergarten(id=KID, name="시험유치원", status="이용중"))
    s.add_all([
        User(id=1, kinder_id=KID, login_id="wonjang", name="김원장",
             role="관리자", password_hash=hash_password("majung1234")),
        User(id=2, kinder_id=KID, login_id="teacher1", name="박선생",
             role="선생님", password_hash=hash_password("majung1234")),
    ])
    s.commit()
    yield s
    s.close()


def _users(db):
    return db.get(User, 1), db.get(User, 2)


def test_초대를_찍으면_그_선생님이_나온다(db):
    owner, teacher = _users(db)
    token = invites.issue(db, teacher, owner, NOW)

    inv = invites.find(db, token, NOW)
    assert inv is not None
    assert inv.user.login_id == "teacher1"
    assert inv.made_by == owner.id


def test_원문은_저장되지_않는다(db):
    """자료가 통째로 새어도 이 표만으로는 아무도 들어올 수 없어야 한다."""
    owner, teacher = _users(db)
    token = invites.issue(db, teacher, owner, NOW)

    row = db.scalar(select(Invite))
    assert token not in row.token_hash
    assert len(row.token_hash) == 64


def test_한_번_쓰면_다시_쓸_수_없다(db):
    owner, teacher = _users(db)
    token = invites.issue(db, teacher, owner, NOW)

    inv = invites.find(db, token, NOW)
    invites.use(db, inv, NOW)
    assert invites.find(db, token, NOW) is None


def test_십분이_지나면_죽는다(db):
    owner, teacher = _users(db)
    token = invites.issue(db, teacher, owner, NOW)

    still = NOW + dt.timedelta(minutes=invites.MINUTES - 1)
    gone = NOW + dt.timedelta(minutes=invites.MINUTES + 1)
    assert invites.find(db, token, still) is not None
    assert invites.find(db, token, gone) is None


def test_새로_만들면_앞의_것은_죽는다(db):
    """두 개가 동시에 돌아다니면 어느 것이 샜는지 알 수 없다."""
    owner, teacher = _users(db)
    old = invites.issue(db, teacher, owner, NOW)
    new = invites.issue(db, teacher, owner, NOW)

    assert invites.find(db, old, NOW) is None
    assert invites.find(db, new, NOW) is not None


def test_엉뚱한_값으로는_찾을_수_없다(db):
    owner, teacher = _users(db)
    token = invites.issue(db, teacher, owner, NOW)

    assert invites.find(db, "", NOW) is None
    assert invites.find(db, token + "x", NOW) is None
    assert invites.find(db, token.upper(), NOW) is None


def test_다_쓴_것은_나중에_치운다(db):
    owner, teacher = _users(db)
    token = invites.issue(db, teacher, owner, NOW)
    invites.use(db, invites.find(db, token, NOW), NOW)

    assert invites.sweep(db, NOW) == 0                                   # 아직 이르다
    assert invites.sweep(db, NOW + dt.timedelta(days=8)) == 1
    assert db.scalar(select(Invite)) is None


def test_주소는_서비스_주소를_쓴다(db, monkeypatch):
    """선생님 휴대폰은 사내망 주소로 들어올 수 없다."""
    monkeypatch.setattr(invites, "PUBLIC_URL", "https://majung.aurabus.co.kr")
    assert invites.link("abc") == "https://majung.aurabus.co.kr/join/abc"
