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


def get_db() -> Iterator[Session]:
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
