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
    Kindergarten,
    PlanEntry,
    Round,
)

MON = dt.date(2026, 9, 7)   # 월요일
SAT = dt.date(2026, 9, 5)   # 토요일


KID = 1   # 시험용 유치원 id


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


def make_child(s, name, room, rnd=None, academy=None, weekday=0):
    c = Child(kinder_id=KID, name=name, class_id=room.id)
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
    room = service.classes(db, KID)[0]
    i1 = service.round_by_key(db, KID, "i1")
    make_child(db, "민준", room, i1)

    row = service.day_rows(db, KID, MON)[0]
    assert row.needs_sign is True


def test_차에_태우면_체크만_한다(db):
    room = service.classes(db, KID)[0]
    b1 = service.round_by_key(db, KID, "b1")
    make_child(db, "서아", room, b1)

    row = service.day_rows(db, KID, MON)[0]
    assert row.needs_sign is False


def test_학원차는_개별_차수여도_서명하지_않는다(db):
    """학원 기사는 매일 오는 정해진 사람이라 체크로 충분하다."""
    room = service.classes(db, KID)[0]
    i1 = service.round_by_key(db, KID, "i1")
    aca = db.query(Academy).first()
    make_child(db, "도윤", room, i1, academy=aca)

    row = service.day_rows(db, KID, MON)[0]
    assert row.is_academy is True
    assert row.needs_sign is False
    assert "태권도" in row.label


def test_결석하면_명단에서_빠진다(db):
    from firstout.models import Attendance

    room = service.classes(db, KID)[0]
    i1 = service.round_by_key(db, KID, "i1")
    c1 = make_child(db, "하윤", room, i1)
    make_child(db, "지우", room, i1)

    db.add(Attendance(child_id=c1.id, on_date=MON, status=ATT_ABSENT, reason="질병"))
    db.commit()

    rows = service.day_rows(db, KID, MON)
    target = service.rows_for_round(rows, i1)
    skipped = service.excluded_for_round(rows, i1)

    assert [r.child.name for r in target] == ["지우"]
    assert [r.child.name for r in skipped] == ["하윤"]


def test_조퇴도_명단에서_빠진다(db):
    from firstout.models import Attendance

    room = service.classes(db, KID)[0]
    care = service.round_by_key(db, KID, "care")
    c = make_child(db, "예준", room, care)
    db.add(Attendance(child_id=c.id, on_date=MON, status=ATT_EARLY, reason="병원"))
    db.commit()

    rows = service.day_rows(db, KID, MON)
    assert service.rows_for_round(rows, care) == []


def test_명단은_반_동선_순서를_따른다(db):
    """가나다순이 아니라 아이를 데려오는 순서로 나와야 한다."""
    jihye, haengbok = service.classes(db, KID)
    i1 = service.round_by_key(db, KID, "i1")
    make_child(db, "가나다", haengbok, i1)   # 이름은 앞서지만 반 순서는 뒤
    make_child(db, "하하하", jihye, i1)

    rows = service.day_rows(db, KID, MON)
    groups = service.group_by_class(service.rows_for_round(rows, i1))
    assert [g[0].name for g in groups] == ["지혜1", "행복1"]


def test_계획이_없는_요일은_명단에_없다(db):
    room = service.classes(db, KID)[0]
    make_child(db, "채원", room, rnd=None)   # 정규 후 귀가

    row = service.day_rows(db, KID, MON)[0]
    assert row.label == "정규"
    assert row.needs_sign is False


def test_반별_집계가_총원과_맞는다(db):
    from firstout.models import Attendance

    room = service.classes(db, KID)[0]
    i1 = service.round_by_key(db, KID, "i1")
    c1 = make_child(db, "가", room, i1)
    make_child(db, "나", room, i1)
    make_child(db, "다", room, i1)
    db.add(Attendance(child_id=c1.id, on_date=MON, status=ATT_ABSENT))
    db.commit()

    rows = service.day_rows(db, KID, MON)
    s = service.class_stats(db, KID, rows, dt.datetime.now())[0]
    assert s.total == s.absent + s.early + s.home + s.staying
    assert s.absent == 1
    assert s.staying == 2


# ── 유치원 분리 ─────────────────────────────────────────
# 한 번 설치해 여러 유치원이 쓰므로, 남의 원 아이가 섞이면 가장 큰 사고다.

def test_다른_유치원_아이는_섞이지_않는다(db):
    other = Kindergarten(id=2, name="다른유치원")
    db.add(other)
    db.add(ClassRoom(id=99, kinder_id=2, name="다른반", seq=0))
    db.commit()

    room = service.classes(db, KID)[0]
    i1 = service.round_by_key(db, KID, "i1")
    make_child(db, "우리아이", room, i1)

    c = Child(kinder_id=2, name="남의아이", class_id=99)
    db.add(c)
    db.flush()
    db.add(PlanEntry(child_id=c.id, weekday=0, round_id=i1.id))
    db.commit()

    names = [r.child.name for r in service.day_rows(db, KID, MON)]
    assert names == ["우리아이"]
    assert [r.child.name for r in service.day_rows(db, 2, MON)] == ["남의아이"]


def test_반과_차수도_유치원별로_나뉜다(db):
    db.add(Kindergarten(id=2, name="다른유치원"))
    db.add(ClassRoom(kinder_id=2, name="다른반", seq=0))
    db.add(Round(kinder_id=2, key="i1", name="다른 1차", kind="개별", seq=0, at_time="14:00"))
    db.commit()

    assert [c.name for c in service.classes(db, KID)] == ["지혜1", "행복1"]
    assert [c.name for c in service.classes(db, 2)] == ["다른반"]
    # 같은 key 라도 유치원이 다르면 다른 차수다
    assert service.round_by_key(db, KID, "i1").at_time == "15:40"
    assert service.round_by_key(db, 2, "i1").at_time == "14:00"


def test_같은_반_이름을_다른_유치원에서_쓸_수_있다(db):
    db.add(Kindergarten(id=2, name="다른유치원"))
    db.commit()
    db.add(ClassRoom(kinder_id=2, name="지혜1", seq=0))
    db.commit()   # 유치원이 다르므로 이름이 겹쳐도 된다

    assert len(service.classes(db, KID)) == 2
    assert len(service.classes(db, 2)) == 1


# ── 출결이 명단에 미치는 영향 ───────────────────────────
# 출결 화면이 하루의 시작점이다. 여기서 잘못되면 안 온 아이를 계속 찾게 된다.

def test_출결을_기록하지_않으면_출석으로_본다(db):
    room = service.classes(db, KID)[0]
    i1 = service.round_by_key(db, KID, "i1")
    make_child(db, "민준", room, i1)

    row = service.day_rows(db, KID, MON)[0]
    assert row.att is None
    assert not row.excluded
    target = service.rows_for_round(service.day_rows(db, KID, MON), i1)
    assert [r.child.name for r in target] == ["민준"]


def test_결석_사유가_명단_아래에_함께_나온다(db):
    from firstout.models import Attendance

    room = service.classes(db, KID)[0]
    i1 = service.round_by_key(db, KID, "i1")
    c = make_child(db, "하윤", room, i1)
    db.add(Attendance(child_id=c.id, on_date=MON, status=ATT_ABSENT, reason="연락없음"))
    db.commit()

    rows = service.day_rows(db, KID, MON)
    skipped = service.excluded_for_round(rows, i1)
    assert len(skipped) == 1
    assert skipped[0].att.reason == "연락없음"


def test_조퇴하면_모든_차수에서_빠진다(db):
    """조퇴는 이미 집에 간 것이므로 어느 명단에도 남으면 안 된다."""
    from firstout.models import Attendance

    room = service.classes(db, KID)[0]
    c = make_child(db, "예준", room, service.round_by_key(db, KID, "care"))
    db.add(Attendance(child_id=c.id, on_date=MON, status=ATT_EARLY, left_at="13:20"))
    db.commit()

    rows = service.day_rows(db, KID, MON)
    for r in service.rounds(db, KID):
        assert service.rows_for_round(rows, r) == []


def test_출결을_되돌리면_명단에_다시_들어온다(db):
    from firstout.models import ATT_PRESENT, Attendance

    room = service.classes(db, KID)[0]
    i1 = service.round_by_key(db, KID, "i1")
    c = make_child(db, "서아", room, i1)
    a = Attendance(child_id=c.id, on_date=MON, status=ATT_ABSENT, reason="질병")
    db.add(a)
    db.commit()
    assert service.rows_for_round(service.day_rows(db, KID, MON), i1) == []

    a.status = ATT_PRESENT
    a.reason = ""
    db.commit()
    back = service.rows_for_round(service.day_rows(db, KID, MON), i1)
    assert [r.child.name for r in back] == ["서아"]


def test_오늘만_다른_차수로_옮기면_그쪽_명단에만_나온다(db):
    """「오늘은 할머니가 데리러 오신대요」 — 주간 계획은 건드리지 않는다."""
    from firstout.models import Departure

    room = service.classes(db, KID)[0]
    i1 = service.round_by_key(db, KID, "i1")
    care = service.round_by_key(db, KID, "care")
    c = make_child(db, "하윤", room, i1)
    db.add(Departure(child_id=c.id, on_date=MON, round_id=care.id, status="대기"))
    db.commit()

    rows = service.day_rows(db, KID, MON)
    assert service.rows_for_round(rows, i1) == []
    moved = service.rows_for_round(rows, care)
    assert [r.child.name for r in moved] == ["하윤"]
    assert moved[0].added_today          # 명단에 「오늘만」으로 표시된다
    assert c.plan[0].round_id == i1.id   # 다음 주 월요일은 그대로 1차 개별


def test_계획대로_나가면_오늘만_표시가_붙지_않는다(db):
    from firstout.models import Departure

    room = service.classes(db, KID)[0]
    i1 = service.round_by_key(db, KID, "i1")
    c = make_child(db, "지호", room, i1)
    db.add(Departure(child_id=c.id, on_date=MON, round_id=i1.id, status="대기"))
    db.commit()

    got = service.rows_for_round(service.day_rows(db, KID, MON), i1)
    assert [r.child.name for r in got] == ["지호"]
    assert not got[0].added_today


def test_오늘만_넣어도_결석이면_명단에_나오지_않는다(db):
    """실수로 넣었더라도 안 온 아이가 명단에 남으면 안 된다."""
    from firstout.models import Attendance, Departure

    room = service.classes(db, KID)[0]
    care = service.round_by_key(db, KID, "care")
    c = make_child(db, "은우", room, service.round_by_key(db, KID, "i1"))
    db.add(Departure(child_id=c.id, on_date=MON, round_id=care.id, status="대기"))
    db.add(Attendance(child_id=c.id, on_date=MON, status=ATT_ABSENT, reason="질병"))
    db.commit()

    rows = service.day_rows(db, KID, MON)
    assert service.rows_for_round(rows, care) == []
    assert [r.child.name for r in service.excluded_for_round(rows, care)] == ["은우"]


def test_승인된_유치원만_목록에_나온다(db):
    """승인대기·정지 상태가 첫 화면에 보이면 안 된다.

    서버를 켤 때도 이 함수를 쓰기 때문에, 여기가 깨지면 아예 뜨지 않는다.
    """
    db.add_all([
        Kindergarten(name="대기유치원", status="승인대기"),
        Kindergarten(name="정지유치원", status="정지"),
    ])
    db.commit()
    assert [k.name for k in service.kindergartens(db)] == ["시험유치원"]


# ── 오늘 챙겨야 할 것 ───────────────────────────────────

def test_연락없음_결석만_따로_모인다(db):
    """오지 않았는데 연락도 닿지 않는 것은 원장이 가장 먼저 알아야 한다."""
    from firstout.models import Attendance

    room = service.classes(db, KID)[0]
    i1 = service.round_by_key(db, KID, "i1")
    a = make_child(db, "서아", room, i1)
    b = make_child(db, "하준", room, i1)
    db.add(Attendance(child_id=a.id, on_date=MON, status=ATT_ABSENT, reason="연락없음"))
    db.add(Attendance(child_id=b.id, on_date=MON, status=ATT_ABSENT, reason="질병"))
    db.commit()

    got = service.no_contact(service.day_rows(db, KID, MON))
    assert [r.child.name for r in got] == ["서아"]


def test_시각이_지나면_남은_아이를_알려준다(db):
    """호출하고 안 오는 것과 다르다 — 아무도 아직 손대지 않은 것이다."""
    room = service.classes(db, KID)[0]
    i1 = service.round_by_key(db, KID, "i1")       # 15:40
    make_child(db, "서아", room, i1)
    rows = service.day_rows(db, KID, MON)

    before = dt.datetime.combine(MON, dt.time(15, 45))   # 5분 지남 — 아직 기다린다
    after = dt.datetime.combine(MON, dt.time(15, 55))    # 15분 지남
    assert service.overdue(rows, i1, before, MON) == []
    assert [r.child.name for r in service.overdue(rows, i1, after, MON)] == ["서아"]


def test_이미_귀가한_아이는_세지_않는다(db):
    from firstout.models import Departure

    room = service.classes(db, KID)[0]
    i1 = service.round_by_key(db, KID, "i1")
    c = make_child(db, "서아", room, i1)
    db.add(Departure(child_id=c.id, on_date=MON, round_id=i1.id, status="완료"))
    db.commit()

    late = dt.datetime.combine(MON, dt.time(16, 30))
    assert service.overdue(service.day_rows(db, KID, MON), i1, late, MON) == []


def test_지난_날짜를_들춰볼_때는_경고하지_않는다(db):
    """그때는 이미 다 끝난 일이다. 붉은 줄만 늘어놓으면 오늘 것이 묻힌다."""
    room = service.classes(db, KID)[0]
    i1 = service.round_by_key(db, KID, "i1")
    make_child(db, "서아", room, i1)

    rows = service.day_rows(db, KID, MON)
    now = dt.datetime.combine(MON + dt.timedelta(days=3), dt.time(16, 30))
    assert service.overdue(rows, i1, now, MON) == []


def test_시각이_이상해도_터지지_않는다(db):
    room = service.classes(db, KID)[0]
    i1 = service.round_by_key(db, KID, "i1")
    make_child(db, "서아", room, i1)
    i1.at_time = "언제쯤"
    db.commit()

    now = dt.datetime.combine(MON, dt.time(23, 0))
    assert service.overdue(service.day_rows(db, KID, MON), i1, now, MON) == []
