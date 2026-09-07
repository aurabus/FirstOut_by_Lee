"""권한과 직함.

시작하는 사람이 늘 원장인 것은 아니다. 원감·주임·담당 선생님일 수도 있다.
그래서 **권한은 관리자/선생님 둘뿐이고, 원장·담임 같은 것은 직함**으로 적는다.
"""

from __future__ import annotations

import sqlite3

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from firstout.models import (
    ADMIN_TITLES,
    ROLE_ADMIN,
    ROLE_OPERATOR,
    ROLE_TEACHER,
    TITLES,
    Base,
    Kindergarten,
    User,
)
from firstout.security import hash_password

KID = 1


@pytest.fixture()
def db():
    engine = create_engine("sqlite://")
    Base.metadata.create_all(engine)
    s = sessionmaker(bind=engine)()
    s.add(Kindergarten(id=KID, name="시험유치원", status="이용중"))
    s.commit()
    yield s
    s.close()


def _user(s, login_id, role, title=""):
    u = User(kinder_id=KID, login_id=login_id, name=login_id, role=role, title=title,
             password_hash=hash_password("majung1234"))
    s.add(u)
    s.commit()
    return u


def test_권한은_두_가지뿐이다():
    """직함이 늘어나도 권한은 늘어나지 않는다 — 늘어나면 누가 무엇을 하는지 흐려진다."""
    assert ROLE_ADMIN == "관리자"
    assert ROLE_TEACHER == "선생님"
    assert ROLE_OPERATOR == "운영자"


def test_직함은_고를_수도_적을_수도_있다():
    assert "원장" in TITLES and "담임" in TITLES and "돌봄" in TITLES
    assert set(ADMIN_TITLES) <= set(TITLES)


def test_관리자만_설정과_계정을_맡는다(db):
    admin = _user(db, "won", ROLE_ADMIN, "주임")
    teacher = _user(db, "kim", ROLE_TEACHER, "담임")
    assert admin.is_admin and not admin.is_operator
    assert not teacher.is_admin


def test_운영자는_어디서나_관리자다(db):
    op = _user(db, "sysop", ROLE_OPERATOR, "서비스 운영")
    assert op.is_operator and op.is_admin


def test_원장이_아니어도_총괄_관리자가_될_수_있다(db):
    """주임 선생님이 시작해도 아무 문제가 없어야 한다."""
    u = _user(db, "jumim", ROLE_ADMIN, "주임")
    assert u.is_admin
    assert u.title == "주임"


# ── 예전 자료 옮기기 ────────────────────────────────────

def test_예전_이름이_새_이름으로_옮겨진다(tmp_path, monkeypatch):
    """이미 쓰던 유치원의 「원장·교사」가 그대로 남으면 권한 검사가 어긋난다."""
    path = tmp_path / "old.db"
    con = sqlite3.connect(path)
    con.executescript(
        "create table user (id integer primary key, login_id text, role text, title text);"
        "insert into user (login_id, role, title) values"
        " ('won', '원장', ''), ('kim', '교사', '지혜1 담임'), ('sysop', '운영자', '서비스 운영');"
    )
    con.commit()
    con.close()

    import firstout.db as fdb

    engine = create_engine(f"sqlite:///{path}")
    monkeypatch.setattr(fdb, "engine", engine)
    fdb._rename_roles()

    con = sqlite3.connect(path)
    got = dict(con.execute("select login_id, role from user").fetchall())
    titles = dict(con.execute("select login_id, title from user").fetchall())
    con.close()

    assert got == {"won": "관리자", "kim": "선생님", "sysop": "운영자"}
    assert titles["won"] == "원장"          # 직함으로 남겨 준다
    assert titles["kim"] == "지혜1 담임"     # 이미 있던 직함은 건드리지 않는다


def test_두_번_옮겨도_같다(tmp_path, monkeypatch):
    path = tmp_path / "twice.db"
    con = sqlite3.connect(path)
    con.executescript(
        "create table user (id integer primary key, login_id text, role text, title text);"
        "insert into user (login_id, role, title) values ('won', '원장', '');"
    )
    con.commit()
    con.close()

    import firstout.db as fdb

    monkeypatch.setattr(fdb, "engine", create_engine(f"sqlite:///{path}"))
    fdb._rename_roles()
    fdb._rename_roles()

    con = sqlite3.connect(path)
    assert con.execute("select role, title from user").fetchall() == [("관리자", "원장")]
    con.close()
