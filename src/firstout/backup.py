"""자동 백업 — 하루 한 벌, 사무실 NAS 가 가져갈 수 있게.

원아 이름·보호자 연락처·귀가 기록이 들어 있는 자료다. 잃어버리면 복구가 안 된다.
서버는 매일 자기 자신의 사본을 `data/backup/` 에 떨궈 두기만 한다. 그 폴더를
NAS(시놀로지)가 가져가면 서버 디스크가 통째로 죽어도 자료는 남는다.

**파일을 그냥 복사하면 안 된다.** WAL 모드라 쓰는 도중에 복사하면 깨진 사본이 나온다.
SQLite 의 `VACUUM INTO` 는 서버를 멈추지 않고 그 시점의 온전한 사본을 만든다.
"""

from __future__ import annotations

import datetime as dt
import sqlite3

from .config import BACKUP_DIR, DB_PATH

KEEP_DAYS = 30
PREFIX = "majung-"


def _target(day: dt.date):
    return BACKUP_DIR / f"{PREFIX}{day}.db"


def run(day: dt.date | None = None) -> tuple[str, int]:
    """오늘 사본을 만들고 오래된 것을 치운다.

    돌려주는 값은 (안내문, 지운 개수). 이미 오늘 것이 있으면 다시 만들지 않는다.
    """
    day = day or dt.date.today()
    BACKUP_DIR.mkdir(parents=True, exist_ok=True)

    out = _target(day)
    if not out.exists():
        if not DB_PATH.exists():
            return ("백업할 자료가 아직 없습니다", 0)
        tmp = out.with_suffix(".part")
        tmp.unlink(missing_ok=True)
        con = sqlite3.connect(DB_PATH)
        try:
            con.execute("VACUUM INTO ?", (str(tmp),))
        finally:
            con.close()
        tmp.replace(out)     # 다 만들어진 뒤에야 제 이름을 준다

    size = out.stat().st_size
    return (f"백업 {out.name} ({size // 1024:,}KB)", sweep(day))


def sweep(day: dt.date | None = None, keep_days: int = KEEP_DAYS) -> int:
    """보관 기간이 지난 사본을 지운다. 여기 남아 있어도 개인정보다."""
    day = day or dt.date.today()
    cutoff = day - dt.timedelta(days=keep_days)
    gone = 0
    for f in BACKUP_DIR.glob(f"{PREFIX}*.db"):
        try:
            on = dt.date.fromisoformat(f.stem[len(PREFIX):])
        except ValueError:
            continue         # 사람이 손으로 둔 파일은 건드리지 않는다
        if on < cutoff:
            try:
                f.unlink()
                gone += 1
            except OSError:
                pass
    return gone


def latest() -> tuple[str, int] | None:
    """가장 최근 백업 (파일 이름, 바이트). 화면에 보여주려고 쓴다."""
    files = sorted(BACKUP_DIR.glob(f"{PREFIX}*.db"))
    if not files:
        return None
    f = files[-1]
    return (f.name, f.stat().st_size)
