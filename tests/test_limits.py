"""가입 신청 속도 제한과 신청 지우기.

주소가 공개된 창구라 밖에서 아무나 두드릴 수 있다. 승인제라 들어오지는 못하지만
**신청 한 번에 스무 줄쯤 만들어지므로** 그대로 두면 운영 화면이 덮인다.
"""

from __future__ import annotations

import datetime as dt

import pytest
from sqlalchemy import create_engine, select
from sqlalchemy.orm import sessionmaker

from firstout import limits
from firstout.models import AuditLog, Base, Kindergarten

IP = "203.0.113.7"


@pytest.fixture()
def db():
    engine = create_engine("sqlite://")
    Base.metadata.create_all(engine)
    s = sessionmaker(bind=engine)()
    yield s
    s.close()


def _try(s, ip=IP, minutes_ago=0, path="/signup", method="POST"):
    s.add(
        AuditLog(
            at=dt.datetime.now() - dt.timedelta(minutes=minutes_ago),
            method=method, path=path, action="가입 신청", status=303, ip=ip,
        )
    )
    s.commit()


def test_아무_기록이_없으면_통과한다(db):
    assert limits.signup_blocked(db, IP) == ""


def test_한_주소에서_잦으면_막는다(db):
    n, _ = limits.SIGNUP_IP_HOUR
    for _ in range(n - 1):
        _try(db)
    assert limits.signup_blocked(db, IP) == ""
    _try(db)
    assert "너무 잦습니다" in limits.signup_blocked(db, IP)


def test_다른_주소는_말려들지_않는다(db):
    """한 곳이 두드린다고 진짜 원장님이 막히면 안 된다."""
    for _ in range(limits.SIGNUP_IP_HOUR[0] + 3):
        _try(db)
    assert limits.signup_blocked(db, "198.51.100.9") == ""


def test_시간이_지나면_다시_열린다(db):
    for _ in range(limits.SIGNUP_IP_HOUR[0] + 1):
        _try(db, minutes_ago=61)
    assert limits.signup_blocked(db, IP) == ""


def test_하루_한도도_본다(db):
    """한 시간마다 조금씩 나눠 두드리는 경우."""
    n, _ = limits.SIGNUP_IP_DAY
    for i in range(n):
        _try(db, minutes_ago=90 * (i + 1))       # 한 시간 한도는 피해 간다
    assert "너무 잦습니다" in limits.signup_blocked(db, IP)


def test_주소를_바꿔가며_들어와도_전체_한도가_있다(db):
    n, _ = limits.SIGNUP_ALL_HOUR
    for i in range(n):
        _try(db, ip=f"198.51.100.{i}")
    assert "몰려 있습니다" in limits.signup_blocked(db, "203.0.113.99")


def test_화면을_열어보는_것은_세지_않는다(db):
    """가입 화면을 구경한 것까지 세면 진짜 원장님이 막힌다."""
    for _ in range(30):
        _try(db, method="GET")
    assert limits.signup_blocked(db, IP) == ""


def test_다른_길은_세지_않는다(db):
    for _ in range(30):
        _try(db, path="/signin")
    assert limits.signup_blocked(db, IP) == ""


# ── 신청 지우기 ─────────────────────────────────────────

def test_승인대기가_아니면_지울_수_없다(db):
    """쓰고 있는 유치원이 잘못 눌러 사라지는 일은 없어야 한다."""
    from firstout.web.operator import KG_PENDING

    db.add_all([
        Kindergarten(id=1, name="대기유치원", status=KG_PENDING),
        Kindergarten(id=2, name="이용중유치원", status="이용중"),
    ])
    db.commit()

    # 화면이 하는 판단과 같은 조건
    ok = [k for k in db.scalars(select(Kindergarten)) if k.status == KG_PENDING]
    assert [k.name for k in ok] == ["대기유치원"]
