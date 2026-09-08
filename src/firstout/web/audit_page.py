"""감사 로그 조회.

총괄 관리자는 자기 유치원 기록만, 운영자는 전체를 본다.
"그때 누가 눌렀나"를 되짚는 화면이라 최근 것이 먼저 보인다.
"""

from __future__ import annotations

import datetime as dt

from fastapi import APIRouter, Depends, Request
from fastapi.responses import RedirectResponse
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from .. import audit, reauth
from ..audit import KEEP_DAYS
from ..db import get_db
from ..models import AuditLog

router = APIRouter()

PER_PAGE = 100


@router.get("/audit")
def audit_view(
    request: Request,
    db: Session = Depends(get_db),
    d: str = "",
    who: str = "",
    only: str = "",
    page_no: int = 1,
):
    from ..main import current_user, page, pick_date

    me = current_user(request, db)
    if me is None:
        return RedirectResponse("/signin", status_code=303)
    if not me.is_admin:
        return RedirectResponse("/board", status_code=303)
    if wall := reauth.wall(request, me):     # 누가 무엇을 했는지가 모두 담긴 화면이다
        return wall

    day = pick_date(d)
    start = dt.datetime.combine(day, dt.time.min)
    end = start + dt.timedelta(days=1)

    q = select(AuditLog).where(AuditLog.at >= start, AuditLog.at < end)
    if not me.is_operator:
        q = q.where(AuditLog.kinder_id == me.kinder_id)   # 내 유치원 것만
    if who:
        q = q.where(AuditLog.user_name == who)
    if only == "change":
        q = q.where(AuditLog.method == "POST")            # 바꾼 것만

    total = db.scalar(select(func.count()).select_from(q.subquery())) or 0
    page_no = max(1, page_no)
    rows = list(
        db.scalars(
            q.order_by(AuditLog.at.desc())
            .offset((page_no - 1) * PER_PAGE)
            .limit(PER_PAGE)
        )
    )

    # 숫자만 보고는 무슨 일인지 알 수 없어, 줄마다 사람 말로 바꿔 붙인다.
    # 화면 이름은 적을 때 붙여 두지만, 이름표가 늘기 전에 쌓인 기록은 영문 주소를
    # 그대로 들고 있다. 보여줄 때 한 번 더 붙여 「/attend」 같은 것이 남지 않게 한다.
    for r in rows:
        r.said = audit.outcome(r.method, r.status, bool(r.user_name), r.path)
        if not r.action or r.action.startswith("/"):
            r.action = audit.describe(r.path)

    names = [
        n
        for (n,) in db.execute(
            select(AuditLog.user_name)
            .where(AuditLog.at >= start, AuditLog.at < end, AuditLog.user_name != "")
            .where(*([] if me.is_operator else [AuditLog.kinder_id == me.kinder_id]))
            .group_by(AuditLog.user_name)
            .order_by(AuditLog.user_name)
        ).all()
    ]

    return page(
        request, "audit.html", db, me,
        day=day, d=d,
        rows=rows, total=total, names=names, who=who, only=only,
        page_no=page_no, pages=max(1, -(-total // PER_PAGE)),
        keep_days=KEEP_DAYS,
    )
