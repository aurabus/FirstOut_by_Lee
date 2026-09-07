"""데이터베이스 연결.

SQLite 파일 하나로 운영한다. 백업이 파일 복사로 끝나는 것이 이 규모에서는 큰 장점이다.
여러 선생님이 동시에 쓰므로 WAL 모드를 켜 읽기가 쓰기에 막히지 않게 한다.
"""

from __future__ import annotations

from collections.abc import Iterator

from sqlalchemy import create_engine, event
from sqlalchemy.orm import Session, sessionmaker

from .config import DB_PATH, ensure_dirs
from .models import Base

ensure_dirs()

engine = create_engine(
    f"sqlite:///{DB_PATH}",
    connect_args={"check_same_thread": False, "timeout": 15},
    future=True,
)


@event.listens_for(engine, "connect")
def _sqlite_pragma(conn, _record):  # noqa: ANN001
    cur = conn.cursor()
    cur.execute("PRAGMA journal_mode=WAL")
    cur.execute("PRAGMA foreign_keys=ON")
    cur.execute("PRAGMA synchronous=NORMAL")
    cur.close()


SessionLocal = sessionmaker(bind=engine, autoflush=False, expire_on_commit=False)


def init_db() -> None:
    Base.metadata.create_all(engine)
    _rename_roles()


def _rename_roles() -> None:
    """예전 이름을 새 이름으로 옮긴다.

    권한 이름을 「원장 → 관리자」, 「교사 → 선생님」으로 바꿨다. 시작하는 사람이
    늘 원장인 것은 아니고(원감·주임·담당 선생님일 수 있다), 원장은 권한이 아니라
    직함이기 때문이다. 이미 쓰던 자료의 원장은 직함에 「원장」을 남겨 준다.

    이미 옮긴 자료에서는 아무 일도 하지 않는다.
    """
    from sqlalchemy import text

    with engine.begin() as conn:
        conn.execute(text(
            "update user set title = '원장' where role = '원장' and (title is null or title = '')"
        ))
        conn.execute(text("update user set role = '관리자' where role = '원장'"))
        conn.execute(text("update user set role = '선생님' where role = '교사'"))


def get_db() -> Iterator[Session]:
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
