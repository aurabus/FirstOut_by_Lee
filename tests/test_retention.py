"""보관 기간 — 오래된 것이 실제로 지워지는지.

「지워집니다」라고 안내해 놓고 남아 있으면 그게 사고다. 시험으로 묶어 둔다.
"""

from __future__ import annotations

import datetime as dt

import pytest
from sqlalchemy import create_engine, select
from sqlalchemy.orm import sessionmaker

from firstout import retention
from firstout.models import Attendance, Base, Departure

TODAY = dt.date(2026, 9, 7)
SIG = "data:image/png;base64,iVBORw0KGgo="


@pytest.fixture()
def db():
    engine = create_engine("sqlite://")
    Base.metadata.create_all(engine)
    s = sessionmaker(bind=engine)()
    yield s
    s.close()


def _dep(s, child_id: int, days_ago: int, sig: str = SIG) -> Departure:
    d = Departure(
        child_id=child_id,
        on_date=TODAY - dt.timedelta(days=days_ago),
        status="완료",
        receiver="박영희 · 모",
        signature=sig,
        done_at=dt.datetime(2026, 9, 7, 15, 45),
    )
    s.add(d)
    s.commit()
    return d


def test_한_달_지난_서명은_지워진다(db, monkeypatch):
    old = _dep(db, 1, days_ago=40)
    monkeypatch.setattr(retention.dt, "date", _fixed_date())

    assert retention.purge_signatures(db) == 1
    db.refresh(old)
    assert old.signature == ""


def test_지워도_인계_기록은_남는다(db, monkeypatch):
    """누가 언제 데려갔는지는 증빙이라 남겨야 한다. 그림만 지운다."""
    old = _dep(db, 1, days_ago=40)
    monkeypatch.setattr(retention.dt, "date", _fixed_date())

    retention.purge_signatures(db)
    db.refresh(old)
    assert old.receiver == "박영희 · 모"
    assert old.status == "완료"
    assert old.done_at is not None
    assert db.scalar(select(Departure).where(Departure.id == old.id)) is not None


def test_한_달_안_된_서명은_그대로다(db, monkeypatch):
    fresh = _dep(db, 1, days_ago=29)
    monkeypatch.setattr(retention.dt, "date", _fixed_date())

    assert retention.purge_signatures(db) == 0
    db.refresh(fresh)
    assert fresh.signature == SIG


def test_같은_날_두_번_돌려도_한_번만_센다(db, monkeypatch):
    _dep(db, 1, days_ago=40)
    _dep(db, 2, days_ago=40, sig="")     # 서명 없이 차량 탑승만 한 아이
    monkeypatch.setattr(retention.dt, "date", _fixed_date())

    assert retention.purge_signatures(db) == 1
    assert retention.purge_signatures(db) == 0


def _fixed_date():
    class D(dt.date):
        @classmethod
        def today(cls):
            return TODAY
    return D


# ── 퇴원한 아이 ─────────────────────────────────────────

def _school(s):
    from firstout.models import Child, ClassRoom, Guardian, Kindergarten, PlanEntry

    s.add(Kindergarten(id=1, name="시험유치원", status="이용중"))
    s.add(ClassRoom(id=1, kinder_id=1, name="지혜1", seq=0))
    s.flush()

    def kid(name, active=True, left=None):
        c = Child(kinder_id=1, name=name, class_id=1, active=active, left_on=left)
        s.add(c)
        s.flush()
        s.add(Guardian(child_id=c.id, name=f"{name}엄마", relation="모",
                       phone="010-1-2", is_default=True, seq=0))
        s.add(PlanEntry(child_id=c.id, weekday=0))
        s.add(Attendance(child_id=c.id, on_date=TODAY, status="출석"))
        s.add(Departure(child_id=c.id, on_date=TODAY, status="완료", receiver="엄마"))
        s.commit()
        return c

    return kid


def test_퇴원하고_한_달_지나면_자료가_지워진다(db, monkeypatch):
    """서명도 감사 로그도 한 달이면 사라지는데, 퇴원한 아이의 이름과 연락처만
    영영 남아 있을 이유가 없다."""
    from firstout.models import Child, Guardian, PlanEntry

    kid = _school(db)
    old = kid("나간아이", active=False, left=TODAY - dt.timedelta(days=40))
    kid("다니는아이")
    monkeypatch.setattr(retention.dt, "date", _fixed_date())

    assert retention.purge_left_children(db) == 1
    assert [c.name for c in db.scalars(select(Child))] == ["다니는아이"]
    # 딸린 것도 함께 사라진다
    assert db.scalar(select(Guardian).where(Guardian.child_id == old.id)) is None
    assert db.scalar(select(PlanEntry).where(PlanEntry.child_id == old.id)) is None
    assert db.scalar(select(Attendance).where(Attendance.child_id == old.id)) is None
    assert db.scalar(select(Departure).where(Departure.child_id == old.id)) is None


def test_한_달_안_된_퇴원생은_그대로다(db, monkeypatch):
    from firstout.models import Child

    kid = _school(db)
    kid("어제나간아이", active=False, left=TODAY - dt.timedelta(days=29))
    monkeypatch.setattr(retention.dt, "date", _fixed_date())

    assert retention.purge_left_children(db) == 0
    assert len(list(db.scalars(select(Child)))) == 1


def test_다니는_아이는_아무리_오래돼도_지우지_않는다(db, monkeypatch):
    """재원 중인 아이는 보관 기간의 대상이 아니다."""
    from firstout.models import Child

    kid = _school(db)
    kid("오래다닌아이", active=True, left=TODAY - dt.timedelta(days=400))
    monkeypatch.setattr(retention.dt, "date", _fixed_date())

    assert retention.purge_left_children(db) == 0
    assert len(list(db.scalars(select(Child)))) == 1


def test_퇴원한_날을_모르면_지우지_않는다(db, monkeypatch):
    """언제 나갔는지 모르는 아이를 날짜 없이 지우면 안 된다."""
    from firstout.models import Child

    kid = _school(db)
    kid("날짜모름", active=False, left=None)
    monkeypatch.setattr(retention.dt, "date", _fixed_date())

    assert retention.purge_left_children(db) == 0
    assert len(list(db.scalars(select(Child)))) == 1


def test_다시_등원하면_세던_것이_멈춘다(db, monkeypatch):
    """복귀한 아이가 며칠 뒤 사라지면 안 된다."""
    from firstout.models import Child

    kid = _school(db)
    c = kid("돌아온아이", active=False, left=TODAY - dt.timedelta(days=40))
    c.active = True
    c.left_on = None                      # 화면(child.leave)이 하는 일
    db.commit()
    monkeypatch.setattr(retention.dt, "date", _fixed_date())

    assert retention.purge_left_children(db) == 0
    assert len(list(db.scalars(select(Child)))) == 1
