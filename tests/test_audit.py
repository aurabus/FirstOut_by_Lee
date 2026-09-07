"""감사 로그 검증.

기록이 쌓이는 것보다 **한 달 뒤 사라지는 것**이 더 중요하다.
오래 남을수록 새어 나갔을 때의 피해만 커지기 때문이다.
"""

from __future__ import annotations

import datetime as dt

import pytest
from sqlalchemy import create_engine, func, select
from sqlalchemy.orm import sessionmaker

from firstout import audit
from firstout.models import AuditLog, Base


@pytest.fixture()
def db():
    engine = create_engine("sqlite://")
    Base.metadata.create_all(engine)
    s = sessionmaker(bind=engine)()
    yield s
    s.close()


def add(db, days_ago: int, path: str = "/board") -> None:
    db.add(AuditLog(at=dt.datetime.now() - dt.timedelta(days=days_ago),
                    user_name="김미영", path=path, action=audit.describe(path),
                    method="GET", status=200))
    db.commit()


def test_한_달_지난_기록은_지워진다(db):
    add(db, 1)      # 어제
    add(db, 29)     # 한 달 안
    add(db, 31)     # 한 달 지남
    add(db, 400)    # 아주 오래됨

    gone = audit.purge_old(db)
    assert gone == 2
    assert db.scalar(select(func.count(AuditLog.id))) == 2


def test_지울_것이_없으면_아무것도_하지_않는다(db):
    add(db, 1)
    assert audit.purge_old(db) == 0
    assert db.scalar(select(func.count(AuditLog.id))) == 1


def test_주소를_사람이_읽는_말로_바꾼다():
    assert audit.describe("/list/i1/12/sign") == "귀가 · 서명 인계"
    assert audit.describe("/list/b1/12/check") == "귀가 · 탑승 체크"
    assert audit.describe("/users/add") == "선생님 계정 추가"
    assert audit.describe("/users/3/reset") == "선생님 비밀번호 재발급"
    assert audit.describe("/operator/2/approve") == "유치원 승인"
    assert audit.describe("/signin") == "로그인"


def test_의미없는_요청은_남기지_않는다():
    """선생님 기기가 10초마다 두드리는 주소까지 남기면 기록이 그것뿐이 된다."""
    assert not audit.should_log("/health")
    assert not audit.should_log("/static/app.css")
    assert not audit.should_log("/favicon.ico")
    assert audit.should_log("/board")
    assert audit.should_log("/list/i1/3/sign")


def test_바꾼_요청과_본_요청을_구분한다():
    assert AuditLog(method="POST").changed
    assert not AuditLog(method="GET").changed
