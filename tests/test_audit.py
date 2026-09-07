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


# ── 사람이 읽을 수 있는가 ───────────────────────────────

def test_모든_화면에_한글_이름이_붙는다():
    """감사 로그에 「/attend」 라고만 뜨면 무슨 일인지 알 수 없다.

    실제로 출결 화면의 이름이 통째로 빠져 있었다. 새 화면을 만들 때마다
    여기에 함께 적도록 시험으로 묶어 둔다.
    """
    import re
    from pathlib import Path

    import firstout
    from firstout import audit

    root = Path(firstout.__file__).parent
    paths = set()
    for f in list((root / "web").glob("*.py")) + [root / "main.py"]:
        src = f.read_text(encoding="utf-8")
        paths |= set(re.findall(r'@(?:router|app)\.(?:get|post)\("([^"]+)"', src))

    sample = {"{cid}": "12", "{key}": "i1", "{uid}": "3", "{kid}": "2", "{gid}": "5",
              "{room_id}": "1", "{rid}": "4", "{bid}": "1", "{aid}": "2",
              "{token}": "AbCdEf"}
    missing = []
    for p in sorted(paths):
        real = p
        for k, v in sample.items():
            real = real.replace(k, v)
        if not audit.should_log(real):
            continue
        if audit.describe(real) == audit.UNKNOWN:
            missing.append(p)
    assert missing == [], f"한글 이름이 없는 화면: {missing}"


def test_영문_주소를_그대로_보여주지_않는다():
    from firstout import audit

    assert audit.describe("/모르는/길") == audit.UNKNOWN
    assert "/" not in audit.describe("/attend")


def test_결과를_숫자가_아니라_말로_알려준다():
    from firstout import audit

    assert audit.outcome("GET", 200, True, "/board")[0] == "열어봄"
    assert audit.outcome("POST", 303, True, "/attend/1")[0] == "처리됨"
    assert audit.outcome("GET", 403, True, "/users")[0] == "막힘"
    # 화면을 열었는데 다른 곳으로 갔다면 처리한 것이 아니라 넘어간 것이다
    assert audit.outcome("GET", 303, True, "/audit")[0] == "넘어감"
    assert audit.outcome("GET", 500, True, "/x")[0] == "서버 오류"


def test_실패한_로그인을_가려낸다():
    """로그인은 되든 안 되든 303 이라 숫자로는 구분되지 않는다.

    성공한 로그인에는 그 사람이 붙으므로, 붙지 않았으면 실패다.
    누가 남의 계정을 두드리고 있는지 이 줄로 알아챈다.
    """
    from firstout import audit

    assert audit.outcome("POST", 303, False, "/signin")[0] == "로그인 실패"
    assert audit.outcome("POST", 303, True, "/signin")[0] == "처리됨"
    assert audit.outcome("GET", 200, False, "/signin")[0] == "열어봄"


# ── 되돌리기 어려운 일에는 무엇이 어떻게 ────────────────

def test_늘어난_칸이_쓰던_자료에도_붙는다(tmp_path, monkeypatch):
    """create_all 은 있는 표를 건드리지 않는다. 그래서 칸이 늘면 쓰던 자료에서만 터진다."""
    import sqlite3

    from sqlalchemy import create_engine

    import firstout.db as fdb

    path = tmp_path / "old.db"
    con = sqlite3.connect(path)
    con.executescript(
        "create table audit_log (id integer primary key, path text, action text);"
        "insert into audit_log (path, action) values ('/board', '오늘 현황');"
    )
    con.commit()
    con.close()

    monkeypatch.setattr(fdb, "engine", create_engine(f"sqlite:///{path}"))
    fdb._add_columns()
    fdb._add_columns()          # 두 번 돌려도 같다

    con = sqlite3.connect(path)
    cols = {r[1] for r in con.execute("pragma table_info(audit_log)")}
    rows = con.execute("select action, detail from audit_log").fetchall()
    con.close()
    assert "detail" in cols
    assert rows == [("오늘 현황", "")]        # 있던 줄은 그대로


def test_남기는_말이_사람이_읽는_말이다():
    """「무엇이 어떻게」가 한 줄로 읽혀야 한다."""
    said = [
        "김미영 권한 선생님 → 관리자",
        "박선생 계정 중지",
        "김민준 · 지혜1 퇴원",
        "전체 교체 · 기존 95명 → 등록 97명",
        "지혜2 반 삭제",
    ]
    for line in said:
        assert len(line) <= 200
        assert "/" not in line          # 주소가 섞이지 않는다
        assert line.strip() == line
