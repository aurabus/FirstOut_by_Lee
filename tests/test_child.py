"""원아 한 명을 고치는 규칙.

명부는 엑셀로 한 번에 올리지만 실제로 바뀌는 건 늘 한 명씩이다.
고친 결과가 **그날 명단에 그대로 반영되는지**가 핵심이다 —
계획만 바뀌고 명단이 그대로면 고친 의미가 없다.
"""

from __future__ import annotations

import datetime as dt

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from firstout import service
from firstout.models import (
    Academy,
    Base,
    Child,
    ClassRoom,
    Guardian,
    Kindergarten,
    PlanEntry,
    Round,
)

MON = dt.date(2026, 9, 7)
KID = 1


@pytest.fixture()
def db():
    engine = create_engine("sqlite://")
    Base.metadata.create_all(engine)
    s = sessionmaker(bind=engine)()
    s.add(Kindergarten(id=KID, name="시험유치원", status="이용중"))
    s.add_all([
        ClassRoom(kinder_id=KID, name="지혜1", seq=0),
        ClassRoom(kinder_id=KID, name="행복1", seq=1),
    ])
    s.add_all([
        Round(kinder_id=KID, key="i1", name="1차 개별", kind="개별", seq=0,
              at_time="15:40", needs_sign=True),
        Round(kinder_id=KID, key="b1", name="1차 차량", kind="차량", seq=1,
              at_time="16:00", needs_sign=False),
    ])
    s.add(Academy(kinder_id=KID, name="태권도"))
    s.commit()
    yield s
    s.close()


def _kid(s, name="서아", room=None):
    room = room or service.classes(s, KID)[0]
    c = Child(kinder_id=KID, name=name, class_id=room.id)
    s.add(c)
    s.flush()
    s.add(Guardian(child_id=c.id, name="박영희", relation="모",
                   phone="010-1234-5678", is_default=True, seq=0))
    s.commit()
    return c


def _set_plan(s, child, weekday, round_id=None, academy_id=None, at=""):
    """child.plan 을 화면과 같은 방식으로 고친다."""
    p = next((x for x in child.plan if x.weekday == weekday), None)
    if p is None:
        p = PlanEntry(child_id=child.id, weekday=weekday)
        s.add(p)
        s.flush()
    p.round_id, p.academy_id, p.time_override = round_id, academy_id, at
    s.commit()
    return p


def test_계획을_고치면_그날_명단이_바뀐다(db):
    """「수요일부터 차량 타요」 — 이게 명단에 안 붙으면 고친 의미가 없다."""
    child = _kid(db)
    i1 = service.round_by_key(db, KID, "i1")
    b1 = service.round_by_key(db, KID, "b1")
    _set_plan(db, child, 0, round_id=i1.id)

    assert [r.child.name for r in service.rows_for_round(service.day_rows(db, KID, MON), i1)] \
        == ["서아"]

    _set_plan(db, child, 0, round_id=b1.id)
    rows = service.day_rows(db, KID, MON)
    assert service.rows_for_round(rows, i1) == []
    assert [r.child.name for r in service.rows_for_round(rows, b1)] == ["서아"]


def test_계획을_비우면_명단에서_빠진다(db):
    """정규 후 귀가 — 어느 명단에도 없어야 한다."""
    child = _kid(db)
    i1 = service.round_by_key(db, KID, "i1")
    _set_plan(db, child, 0, round_id=i1.id)
    _set_plan(db, child, 0, round_id=None)

    rows = service.day_rows(db, KID, MON)
    for r in service.rounds(db, KID):
        assert service.rows_for_round(rows, r) == []


def test_학원차는_서명을_받지_않는다(db):
    """학원차는 매일 정해진 기사가 태우므로 체크만 한다."""
    child = _kid(db)
    i1 = service.round_by_key(db, KID, "i1")
    aca = db.query(Academy).one()
    _set_plan(db, child, 0, round_id=i1.id, academy_id=aca.id)

    row = service.rows_for_round(service.day_rows(db, KID, MON), i1)[0]
    assert row.is_academy
    assert not row.needs_sign
    assert row.label == "학원차 태권도"


def test_요일별로_따로_간다(db):
    """월요일을 고쳐도 화요일은 그대로여야 한다."""
    child = _kid(db)
    i1 = service.round_by_key(db, KID, "i1")
    b1 = service.round_by_key(db, KID, "b1")
    _set_plan(db, child, 0, round_id=i1.id)
    _set_plan(db, child, 1, round_id=b1.id)

    tue = MON + dt.timedelta(days=1)
    assert [r.child.name for r in
            service.rows_for_round(service.day_rows(db, KID, MON), i1)] == ["서아"]
    assert [r.child.name for r in
            service.rows_for_round(service.day_rows(db, KID, tue), b1)] == ["서아"]
    assert service.rows_for_round(service.day_rows(db, KID, tue), i1) == []


def test_시각을_따로_적으면_그것을_쓴다(db):
    child = _kid(db)
    i1 = service.round_by_key(db, KID, "i1")
    _set_plan(db, child, 0, round_id=i1.id, at="16:10")

    row = service.rows_for_round(service.day_rows(db, KID, MON), i1)[0]
    assert row.at_time == "16:10"

    _set_plan(db, child, 0, round_id=i1.id, at="")
    row = service.rows_for_round(service.day_rows(db, KID, MON), i1)[0]
    assert row.at_time == "15:40"          # 차수의 기준 시각


def test_퇴원하면_명단에서_빠지고_되돌릴_수_있다(db):
    """지난 기록이 사라지면 「그때 누가 데려갔나」를 되짚을 수 없다."""
    child = _kid(db)
    i1 = service.round_by_key(db, KID, "i1")
    _set_plan(db, child, 0, round_id=i1.id)

    child.active = False
    db.commit()
    assert service.rows_for_round(service.day_rows(db, KID, MON), i1) == []
    assert db.get(Child, child.id) is not None      # 지우지 않는다

    child.active = True
    db.commit()
    assert len(service.rows_for_round(service.day_rows(db, KID, MON), i1)) == 1


def test_반을_옮기면_명단_순서가_바뀐다(db):
    """명단 순서는 아이를 데려오는 동선이다."""
    rooms = service.classes(db, KID)
    a = _kid(db, "서아", rooms[1])          # 행복1
    b = _kid(db, "하준", rooms[0])          # 지혜1
    i1 = service.round_by_key(db, KID, "i1")
    _set_plan(db, a, 0, round_id=i1.id)
    _set_plan(db, b, 0, round_id=i1.id)

    got = service.rows_for_round(service.day_rows(db, KID, MON), i1)
    assert [r.child.name for r in got] == ["하준", "서아"]

    a.class_id = rooms[0].id                # 지혜1 로 옮긴다
    db.commit()
    got = service.rows_for_round(service.day_rows(db, KID, MON), i1)
    assert [(r.child.classroom.name) for r in got] == ["지혜1", "지혜1"]


def test_기본_인계자는_한_명뿐이다(db):
    """서명 창에 먼저 뜨는 분. 둘이면 어느 쪽이 뜰지 알 수 없다."""
    child = _kid(db)
    db.add(Guardian(child_id=child.id, name="김철수", relation="부", seq=1))
    db.commit()
    db.refresh(child)

    for g in child.guardians:               # 화면이 하는 일
        g.is_default = g.name == "김철수"
    db.commit()
    db.refresh(child)

    assert sum(1 for g in child.guardians if g.is_default) == 1
    assert child.default_guardian.name == "김철수"
