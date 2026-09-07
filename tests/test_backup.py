"""자동 백업 — 사본이 실제로 만들어지고, 실제로 열리는지.

백업의 대부분은 「복구해 본 적이 없어서」 실패한다.
그래서 만든 사본을 다시 열어 자료가 들어 있는지까지 확인한다.
"""

from __future__ import annotations

import datetime as dt
import sqlite3

import pytest

from firstout import backup

TODAY = dt.date(2026, 9, 7)


@pytest.fixture()
def home(tmp_path, monkeypatch):
    """임시 폴더에 진짜 SQLite 파일을 하나 두고 그것을 백업한다."""
    dbf = tmp_path / "majung.db"
    con = sqlite3.connect(dbf)
    con.execute("create table child (id integer primary key, name text)")
    con.execute("insert into child (name) values ('서아'), ('하준')")
    con.commit()
    con.close()

    out = tmp_path / "backup"
    monkeypatch.setattr(backup, "DB_PATH", dbf)
    monkeypatch.setattr(backup, "BACKUP_DIR", out)
    return dbf, out


def test_사본이_만들어지고_다시_열린다(home):
    dbf, out = home
    note, _ = backup.run(TODAY)

    made = out / "majung-2026-09-07.db"
    assert made.exists()
    assert made.name in note

    con = sqlite3.connect(made)
    assert con.execute("select name from child order by id").fetchall() == [("서아",), ("하준",)]
    con.close()


def test_같은_날_두_번_돌려도_한_벌만_남는다(home):
    _, out = home
    backup.run(TODAY)
    first = (out / "majung-2026-09-07.db").stat().st_mtime_ns
    backup.run(TODAY)
    assert (out / "majung-2026-09-07.db").stat().st_mtime_ns == first
    assert len(list(out.glob("majung-*.db"))) == 1


def test_만들다_멈춘_찌꺼기는_남지_않는다(home):
    _, out = home
    backup.run(TODAY)
    assert list(out.glob("*.part")) == []


def test_보관_기간이_지난_사본은_치운다(home):
    _, out = home
    out.mkdir(parents=True, exist_ok=True)
    for name in ("majung-2026-07-01.db", "majung-2026-08-31.db", "majung-2026-09-06.db"):
        (out / name).write_bytes(b"x")

    _, gone = backup.run(TODAY)
    assert gone == 1                                    # 7월 1일 것만 기간이 지났다
    left = sorted(f.name for f in out.glob("majung-*.db"))
    assert left == ["majung-2026-08-31.db", "majung-2026-09-06.db", "majung-2026-09-07.db"]


def test_사람이_둔_파일은_건드리지_않는다(home):
    """NAS 로 옮기기 전에 손으로 이름을 바꿔 둔 사본이 사라지면 곤란하다."""
    _, out = home
    out.mkdir(parents=True, exist_ok=True)
    keep = out / "majung-이전서버.db"
    keep.write_bytes(b"x")

    backup.run(TODAY)
    assert keep.exists()


def test_가장_최근_사본을_알려준다(home):
    _, out = home
    assert backup.latest() is None
    backup.run(TODAY)
    name, size = backup.latest()
    assert name == "majung-2026-09-07.db"
    assert size > 0
