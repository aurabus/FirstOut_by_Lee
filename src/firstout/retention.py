"""보관 기간 — 오래된 것은 지운다.

서명은 손글씨 그림이라 그 자체로 개인정보이고, 쌓이면 자료도 무거워진다.
**한 달이 지나면 그림만 지운다.** 누가 언제 누구에게 데려갔는지(기록)는 남으므로
나중에 되짚는 데는 지장이 없고, 새어 나갔을 때의 피해만 줄어든다.

감사 로그(audit.purge_old)와 같은 기간을 쓴다. 하나만 오래 남으면 의미가 없다.
"""

from __future__ import annotations

import datetime as dt

from sqlalchemy import func, select, update
from sqlalchemy.orm import Session

from .models import Departure

KEEP_DAYS = 30


def purge_signatures(db: Session, keep_days: int = KEEP_DAYS) -> int:
    """한 달 지난 서명 그림을 지운다. 지운 건수를 돌려준다."""
    cutoff = dt.date.today() - dt.timedelta(days=keep_days)
    n = db.scalar(
        select(func.count(Departure.id)).where(
            Departure.on_date < cutoff, Departure.signature != ""
        )
    )
    if n:
        db.execute(
            update(Departure)
            .where(Departure.on_date < cutoff, Departure.signature != "")
            .values(signature="")
        )
        db.commit()
    return int(n or 0)
