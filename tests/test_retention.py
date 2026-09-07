"""보관 기간 — 오래된 것이 실제로 지워지는지.

「지워집니다」라고 안내해 놓고 남아 있으면 그게 사고다. 시험으로 묶어 둔다.
"""

from __future__ import annotations

import datetime as dt

import pytest
from sqlalchemy import create_engine, select
from sqlalchemy.orm import sessionmaker

from firstout import retention
from firstout.models import Base, Departure

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
