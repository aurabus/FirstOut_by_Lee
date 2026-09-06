"""업무 규칙 검증.

화면보다 규칙이 틀리는 게 위험하다. 특히 서명 여부와 명단 제외는 안전과 직결된다.
"""

from __future__ import annotations

import datetime as dt

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from firstout import service
from firstout.models import (
    ATT_ABSENT,
    ATT_EARLY,
    Academy,
    Base,
    Child,
    ClassRoom,
    Guardian,
    PlanEntry,
    Round,
)

MON = dt.date(2026, 9, 7)   # 월요일
SAT = dt.date(2026, 9, 5)   # 토요일


@pytest.fixture()
def db():
    engine = create_engine("sqlite://")
    Base.metadata.create_all(engine)
    s = sessionmaker(bind=engine)()

    rooms = [ClassRoom(name="지혜1", seq=0), ClassRoom(name="행복1", seq=1)]
    s.add_all(rooms)
    rnds = [
        Round(key="i1", name="1차 개별", kind="개별", seq=0, at_time="15:40", needs_sign=True),
        Round(key="b1", name="1차 차량", kind="차량", seq=1, at_time="16:00", needs_sign=False),
        Round(key="care", name="돌봄", kind="돌봄", seq=2, at_time="19:00", needs_sign=True),
    ]
    s.add_all(rnds)
    s.add(Academy(name="태권도"))
    s.commit()
    yield s
    s.close()


def make_child(s, name, room, rnd=None, academy=None, weekday=0):
    c = Child(name=name, class_id=room.id)
    s.add(c)
    s.flush()
    s.add(Guardian(child_id=c.id, name="박영희", relation="모", is_default=True, seq=0))
    s.add(Guardian(child_id=c.id, name="김철수", relation="부", seq=1))
    s.add(
        PlanEntry(
            child_id=c.id,
            weekday=weekday,
            round_id=rnd.id if rnd else None,
            academy_id=academy.id if academy else None,
        )
    )
    s.commit()
    return c


def test_주말에는_계획이_없다(db):
    assert service.weekday_index(MON) == 0
    assert service.weekday_index(SAT) is None


def test_보호자에게_건네면_서명을_받는다(db):
    room = service.classes(db)[0]
    i1 = service.round_by_key(db, "i1")
    make_child(db, "민준", room, i1)

    row = service.day_rows(db, MON)[0]
    assert row.needs_sign is True


def test_차에_태우면_체크만_한다(db):
    room = service.classes(db)[0]
    b1 = service.round_by_key(db, "b1")
    make_child(db, "서아", room, b1)

    row = service.day_rows(db, MON)[0]
    assert row.needs_sign is False


def test_학원차는_개별_차수여도_서명하지_않는다(db):
    """학원 기사는 매일 오는 정해진 사람이라 체크로 충분하다."""
    room = service.classes(db)[0]
    i1 = service.round_by_key(db, "i1")
    aca = db.query(Academy).first()
    make_child(db, "도윤", room, i1, academy=aca)

    row = service.day_rows(db, MON)[0]
    assert row.is_academy is True
    assert row.needs_sign is False
    assert "태권도" in row.label


def test_결석하면_명단에서_빠진다(db):
    from firstout.models import Attendance

    room = service.classes(db)[0]
    i1 = service.round_by_key(db, "i1")
    c1 = make_child(db, "하윤", room, i1)
    make_child(db, "지우", room, i1)

    db.add(Attendance(child_id=c1.id, on_date=MON, status=ATT_ABSENT, reason="질병"))
    db.commit()

    rows = service.day_rows(db, MON)
    target = service.rows_for_round(rows, i1)
    skipped = service.excluded_for_round(rows, i1)

    assert [r.child.name for r in target] == ["지우"]
    assert [r.child.name for r in skipped] == ["하윤"]


def test_조퇴도_명단에서_빠진다(db):
    from firstout.models import Attendance

    room = service.classes(db)[0]
    care = service.round_by_key(db, "care")
    c = make_child(db, "예준", room, care)
    db.add(Attendance(child_id=c.id, on_date=MON, status=ATT_EARLY, reason="병원"))
    db.commit()

    rows = service.day_rows(db, MON)
    assert service.rows_for_round(rows, care) == []


def test_명단은_반_동선_순서를_따른다(db):
    """가나다순이 아니라 아이를 데려오는 순서로 나와야 한다."""
    jihye, haengbok = service.classes(db)
    i1 = service.round_by_key(db, "i1")
    make_child(db, "가나다", haengbok, i1)   # 이름은 앞서지만 반 순서는 뒤
    make_child(db, "하하하", jihye, i1)

    rows = service.day_rows(db, MON)
    groups = service.group_by_class(service.rows_for_round(rows, i1))
    assert [g[0].name for g in groups] == ["지혜1", "행복1"]


def test_계획이_없는_요일은_명단에_없다(db):
    room = service.classes(db)[0]
    make_child(db, "채원", room, rnd=None)   # 정규 후 귀가

    row = service.day_rows(db, MON)[0]
    assert row.label == "정규"
    assert row.needs_sign is False


def test_반별_집계가_총원과_맞는다(db):
    from firstout.models import Attendance

    room = service.classes(db)[0]
    i1 = service.round_by_key(db, "i1")
    c1 = make_child(db, "가", room, i1)
    make_child(db, "나", room, i1)
    make_child(db, "다", room, i1)
    db.add(Attendance(child_id=c1.id, on_date=MON, status=ATT_ABSENT))
    db.commit()

    rows = service.day_rows(db, MON)
    s = service.class_stats(db, rows, dt.datetime.now())[0]
    assert s.total == s.absent + s.early + s.home + s.staying
    assert s.absent == 1
    assert s.staying == 2
