"""명부 엑셀 — 내려받은 파일이 그대로 다시 올라가야 한다.

선생님이 내려받아 고친 뒤 다시 올리는 게 실제 사용법이고,
서버가 잘못됐을 때 손에 남는 마지막 사본이기도 하다.
그래서 「내보내기 → 읽어들이기」가 한 바퀴 도는지를 시험으로 묶어 둔다.
"""

from __future__ import annotations

import pytest
from sqlalchemy import create_engine, select
from sqlalchemy.orm import sessionmaker

from firstout import excel, service
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
        Round(kinder_id=KID, key="care", name="돌봄", kind="돌봄", seq=2,
              at_time="19:00", needs_sign=True),
    ])
    s.add(Academy(kinder_id=KID, name="태권도"))
    s.commit()
    yield s
    s.close()


def _seed(s):
    """요일마다 다른 아이 둘 — 학원차, 시각 지정, 빈 요일을 모두 담는다."""
    rooms = {c.name: c for c in service.classes(s, KID)}
    rnds = {r.name: r for r in service.rounds(s, KID)}
    aca = s.query(Academy).one()

    a = Child(kinder_id=KID, name="서아", class_id=rooms["지혜1"].id, note="땅콩 알레르기")
    b = Child(kinder_id=KID, name="하준", class_id=rooms["행복1"].id)
    s.add_all([a, b])
    s.flush()

    s.add_all([
        Guardian(child_id=a.id, name="박영희", relation="모",
                 phone="010-1234-5678", is_default=True, seq=0),
        Guardian(child_id=a.id, name="김철수", relation="부",
                 phone="010-2345-6789", seq=1),
        Guardian(child_id=b.id, name="최지영", relation="모",
                 phone="010-3456-7890", is_default=True, seq=0),
    ])
    s.add_all([
        PlanEntry(child_id=a.id, weekday=0, round_id=rnds["1차 개별"].id),
        PlanEntry(child_id=a.id, weekday=1, academy_id=aca.id,
                  round_id=rnds["1차 개별"].id),
        PlanEntry(child_id=a.id, weekday=2, round_id=rnds["돌봄"].id),
        PlanEntry(child_id=a.id, weekday=3),                     # 그날은 명단에 없다
        PlanEntry(child_id=a.id, weekday=4, round_id=rnds["1차 차량"].id,
                  time_override="16:10"),
        PlanEntry(child_id=b.id, weekday=0, round_id=rnds["1차 차량"].id),
    ])
    s.commit()
    return a, b


def test_내려받은_명부를_그대로_다시_올릴_수_있다(db):
    _seed(db)
    data = excel.export_roster(db, KID)

    p = excel.parse(data, db, KID)
    assert not p.fatal
    assert [r.problems for r in p.rows] == [[], []]      # 잘못된 줄이 없어야 한다
    assert [r.name for r in p.good] == ["서아", "하준"]   # 반 순서 → 이름 순서


def test_요일별_귀가_방법이_그대로_실려_나온다(db):
    _seed(db)
    p = excel.parse(excel.export_roster(db, KID), db, KID)
    seo = next(r for r in p.good if r.name == "서아")

    assert seo.cls == "지혜1"
    assert seo.days == ["1차 개별", "학원(태권도)", "돌봄", "", "1차 차량 16:10"]
    assert seo.note == "땅콩 알레르기"


def test_기본_인계자가_보호자1_자리에_온다(db):
    """올린 파일에서는 보호자1이 기본 인계자가 된다. 순서가 뒤집히면 안 된다."""
    a, _ = _seed(db)
    a.guardians[0].is_default = False
    a.guardians[1].is_default = True     # 아버지를 기본으로 바꾼다
    db.commit()

    p = excel.parse(excel.export_roster(db, KID), db, KID)
    seo = next(r for r in p.good if r.name == "서아")
    assert seo.guardians[0][:2] == ("김철수", "부")


def _plans(db):
    """아이별 「무슨 요일에 어떻게 나가는가」. 빈 요일은 세지 않는다."""
    return {
        c.name: sorted(
            (p.weekday, p.round.name if p.round else "",
             p.academy.name if p.academy else "", p.time_override)
            for p in c.plan
            if p.round_id or p.academy_id
        )
        for c in db.scalars(select(Child))
    }


def test_한_바퀴_돌아도_계획이_그대로다(db):
    """내려받아 → 지우고 → 다시 올려도 같은 명단이 나와야 한다.

    NAS 로 백업이 안 되는 상황에서 이 파일이 마지막 사본이 되므로,
    한 바퀴 도는 동안 무엇 하나 흘리면 안 된다.
    """
    _seed(db)
    data = excel.export_roster(db, KID)
    before = _plans(db)

    assert excel.apply(data, db, KID, mode="replace") == (2, 0)
    assert _plans(db) == before


def test_원아가_없어도_양식은_나온다(db):
    """명부가 비어 있을 때 내려받기를 눌러도 터지면 안 된다."""
    data = excel.export_roster(db, KID)
    assert data[:2] == b"PK"
    assert excel.parse(data, db, KID).fatal        # 읽을 원아가 없다고 알려준다


# ── 다시 올리기 ─────────────────────────────────────────

def test_이미_있는_아이는_두_번_들어가지_않는다(db):
    """「한 명 추가하려고 파일을 다시 올린다」가 가장 흔한 사용법이다.

    그때마다 전원이 두 줄이 되면 귀가 명단에 같은 아이가 두 번 나오고,
    한쪽만 서명한 채 다른 쪽이 남는다. 안전 문제다.
    """
    _seed(db)
    data = excel.export_roster(db, KID)

    made, changed = excel.apply(data, db, KID, mode="add")
    assert (made, changed) == (0, 0)
    assert len(list(db.scalars(select(Child)))) == 2


def test_다시_올릴_때_새_아이만_들어온다(db):
    _seed(db)
    rooms = {c.name: c for c in service.classes(db, KID)}
    p = excel.parse(excel.export_roster(db, KID), db, KID)
    assert [r.name for r in p.known] == ["서아", "하준"]
    assert p.fresh == []

    # 파일에 한 명을 더 얹는다
    c = Child(kinder_id=KID, name="새친구", class_id=rooms["지혜1"].id)
    db.add(c)
    db.flush()
    db.add(Guardian(child_id=c.id, name="새엄마", relation="모", is_default=True, seq=0))
    db.commit()
    data = excel.export_roster(db, KID)
    db.delete(c)
    db.commit()

    made, changed = excel.apply(data, db, KID, mode="add")
    assert (made, changed) == (1, 0)
    names = sorted(x.name for x in db.scalars(select(Child)))
    assert names == ["새친구", "서아", "하준"]


def test_맞추기를_고르면_계획이_갱신된다(db):
    """「목요일부터 차량이에요」를 엑셀로 고쳐 올리는 경우."""
    a, _ = _seed(db)
    rnds = {r.name: r for r in service.rounds(db, KID)}
    before = {p.weekday: p.round_id for p in a.plan}
    assert before[3] is None                       # 목요일은 비어 있었다

    data = excel.export_roster(db, KID)
    for p in a.plan:
        if p.weekday == 3:
            p.round_id = rnds["1차 차량"].id       # 서버 쪽만 바꿔두고
    db.commit()

    made, changed = excel.apply(data, db, KID, mode="update")
    assert (made, changed) == (0, 2)
    a2 = db.scalar(select(Child).where(Child.name == "서아"))
    assert {p.weekday: p.round_id for p in a2.plan}[3] is None   # 파일 기준으로 되돌아온다


def test_맞추기는_보호자도_파일_기준으로_바꾼다(db):
    a, _ = _seed(db)
    data = excel.export_roster(db, KID)
    db.add(Guardian(child_id=a.id, name="임시이모", relation="이모", seq=9))
    db.commit()
    assert len(a.guardians) == 3

    excel.apply(data, db, KID, mode="update")
    a2 = db.scalar(select(Child).where(Child.name == "서아"))
    assert sorted(g.name for g in a2.guardians) == ["김철수", "박영희"]


def test_반이_바뀌어도_같은_아이로_본다(db):
    """진급하면 반이 바뀐다. 그때 두 줄이 되면 안 된다."""
    a, _ = _seed(db)
    rooms = service.classes(db, KID)
    data = excel.export_roster(db, KID)
    a.class_id = rooms[1].id
    db.commit()

    p = excel.parse(data, db, KID)
    assert [r.name for r in p.known] == ["서아", "하준"]
    made, changed = excel.apply(data, db, KID, mode="update")
    assert made == 0
    assert len(list(db.scalars(select(Child)))) == 2
