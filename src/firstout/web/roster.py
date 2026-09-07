"""원아 명부 — 주간 귀가 계획.

아이 한 명이 한 줄. 이 표에서 매일 차수별 명단이 자동으로 만들어진다.
"""

from __future__ import annotations

import datetime as dt

from fastapi import APIRouter, Depends, Request
from fastapi.responses import RedirectResponse
from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload

from .. import excel, reauth, service
from ..db import get_db
from ..models import Child, PlanEntry
from . import xlsx

router = APIRouter()


@router.get("/roster")
def roster(
    request: Request,
    cls: int | None = None,
    q: str = "",
    db: Session = Depends(get_db),
):
    from ..main import current_user, page

    me = current_user(request, db)
    if me is None:
        return RedirectResponse("/signin", status_code=303)

    stmt = (
        select(Child)
        .where(Child.active.is_(True), Child.kinder_id == me.kinder_id)
        .options(
            selectinload(Child.classroom),
            selectinload(Child.guardians),
            selectinload(Child.plan).selectinload(PlanEntry.round),
            selectinload(Child.plan).selectinload(PlanEntry.academy),
        )
    )
    if cls:
        stmt = stmt.where(Child.class_id == cls)
    kids = list(db.scalars(stmt))

    if q:
        kids = [k for k in kids if q in k.name or q in k.classroom.name]

    order = {c.id: c.seq for c in service.classes(db, me.kinder_id)}
    kids.sort(key=lambda k: (order.get(k.class_id, 99), k.name))

    # 요일별 계획을 화면에서 바로 꺼내 쓰도록 표로 만든다
    plans = {
        k.id: {p.weekday: p for p in k.plan}
        for k in kids
    }
    return page(
        request, "roster.html", db, me,
        kids=kids, plans=plans, sel_cls=cls, q=q,
    )


@router.get("/roster/export")
def export(request: Request, db: Session = Depends(get_db)):
    """지금 명부를 엑셀로 내려받는다.

    올릴 때와 같은 양식이라 고쳐서 그대로 다시 올릴 수 있고,
    서버에 문제가 생겼을 때 선생님 손에 남는 마지막 사본이 된다.
    """
    from ..main import current_user

    me = current_user(request, db)
    if me is None:
        return RedirectResponse("/signin", status_code=303)
    if me.kinder_id is None:
        return RedirectResponse("/", status_code=303)
    if wall := reauth.wall(request, me):     # 보호자 연락처가 파일로 나간다
        return wall

    data = excel.export_roster(db, me.kinder_id)
    today = dt.date.today()
    return xlsx(data, f"원아명부_{me.kinder.name}_{today}.xlsx", f"majung_roster_{today}.xlsx")
