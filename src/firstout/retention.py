"""보관 기간 — 오래된 것은 지운다.

서명은 손글씨 그림이라 그 자체로 개인정보이고, 쌓이면 자료도 무거워진다.
**한 달이 지나면 그림만 지운다.** 누가 언제 누구에게 데려갔는지(기록)는 남으므로
나중에 되짚는 데는 지장이 없고, 새어 나갔을 때의 피해만 줄어든다.

감사 로그(audit.purge_old)와 같은 기간을 쓴다. 하나만 오래 남으면 의미가 없다.
"""

from __future__ import annotations

import datetime as dt

from sqlalchemy import delete, func, select, update
from sqlalchemy.orm import Session

from .models import Attendance, Child, Departure

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


def purge_left_children(db: Session, keep_days: int = KEEP_DAYS) -> int:
    """퇴원하고 한 달이 지난 아이의 자료를 지운다.

    다른 것과 같은 기간을 쓴다. 서명도 감사 로그도 한 달이면 사라지는데
    퇴원한 아이의 이름과 보호자 연락처만 영영 남아 있을 이유가 없다.

    지우는 것은 그 아이에 딸린 전부다 — 출결·귀가 기록·주간 계획·인계자.
    되돌릴 수 없으므로 **퇴원 처리 화면에서 미리 알려준다.**
    다시 등원하면 left_on 을 비우므로 세던 것이 멈춘다.
    """
    cutoff = dt.date.today() - dt.timedelta(days=keep_days)
    gone = list(
        db.scalars(
            select(Child.id).where(
                Child.active.is_(False),
                Child.left_on.is_not(None),
                Child.left_on < cutoff,
            )
        )
    )
    if not gone:
        return 0

    # 아이를 가리키는 표를 먼저 비운다. 관계로 이어진 것(인계자·주간 계획)은
    # Child 를 지울 때 함께 사라지지만, 출결과 귀가 기록은 그렇지 않다.
    db.execute(delete(Attendance).where(Attendance.child_id.in_(gone)))
    db.execute(delete(Departure).where(Departure.child_id.in_(gone)))
    for c in db.scalars(select(Child).where(Child.id.in_(gone))):
        db.delete(c)
    db.commit()
    return len(gone)
