"""처음 시작하는 원장에게 보여줄 안내.

다 해놓고도 계속 뜨면 잔소리가 되고, 안 뜨면 거기서 멈춘다.
「끝나면 사라진다」가 이 기능의 전부다.
"""

from __future__ import annotations

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from firstout import setup_guide
from firstout.models import ROLE_ADMIN, ROLE_TEACHER, Base, Child, Kindergarten, User
from firstout.security import hash_password
from firstout.seed import fill_new_kinder

KID = 1


@pytest.fixture()
def db():
    engine = create_engine("sqlite://")
    Base.metadata.create_all(engine)
    s = sessionmaker(bind=engine)()
    k = Kindergarten(id=KID, name="새유치원", status="이용중")
    s.add(k)
    s.flush()
    fill_new_kinder(s, k)
    s.add(User(kinder_id=KID, login_id="won", name="원장님", role=ROLE_ADMIN,
               password_hash=hash_password("majung1234")))
    s.commit()
    yield s
    s.close()


def test_승인_직후에는_네_가지가_모두_남아_있다(db):
    left = setup_guide.remaining(db, KID)
    assert [s.key for s in left] == ["class", "round", "roster", "teacher"]
    assert all(s.where.startswith("/") for s in left)


def test_반_이름을_바꾸면_그_단계가_사라진다(db):
    from firstout import service

    rooms = service.classes(db, KID)
    rooms[0].name = "햇살1"
    db.commit()
    assert "class" not in [s.key for s in setup_guide.remaining(db, KID)]


def test_차수_시각을_고치면_그_단계가_사라진다(db):
    from firstout import service

    service.rounds(db, KID)[0].at_time = "15:50"
    db.commit()
    assert "round" not in [s.key for s in setup_guide.remaining(db, KID)]


def test_원아를_넣으면_명부_단계가_사라진다(db):
    from firstout import service

    db.add(Child(kinder_id=KID, name="서아", class_id=service.classes(db, KID)[0].id))
    db.commit()
    assert "roster" not in [s.key for s in setup_guide.remaining(db, KID)]


def test_선생님을_넣으면_초대_단계가_사라진다(db):
    db.add(User(kinder_id=KID, login_id="t1", name="김선생", role=ROLE_TEACHER,
                password_hash=hash_password("majung1234")))
    db.commit()
    assert "teacher" not in [s.key for s in setup_guide.remaining(db, KID)]


def test_관리자만_있는_것은_선생님으로_치지_않는다(db):
    """총괄 관리자 혼자서는 반을 맡을 수 없다."""
    assert "teacher" in [s.key for s in setup_guide.remaining(db, KID)]


def test_그만둔_선생님은_세지_않는다(db):
    db.add(User(kinder_id=KID, login_id="t1", name="김선생", role=ROLE_TEACHER,
                active=False, password_hash=hash_password("majung1234")))
    db.commit()
    assert "teacher" in [s.key for s in setup_guide.remaining(db, KID)]


def test_네_가지를_다_하면_안내가_사라진다(db):
    from firstout import service

    service.classes(db, KID)[0].name = "햇살1"
    service.rounds(db, KID)[0].at_time = "15:50"
    db.add(Child(kinder_id=KID, name="서아", class_id=service.classes(db, KID)[0].id))
    db.add(User(kinder_id=KID, login_id="t1", name="김선생", role=ROLE_TEACHER,
                password_hash=hash_password("majung1234")))
    db.commit()
    assert setup_guide.remaining(db, KID) == []
    assert all(s.done for s in setup_guide.steps(db, KID))
