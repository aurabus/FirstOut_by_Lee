"""원아 명부 — 주간 귀가 계획.

아이 한 명이 한 줄. 이 표에서 매일 차수별 명단이 자동으로 만들어진다.
"""

from __future__ import annotations

from fastapi import APIRouter, Depends, Request
from fastapi.responses import RedirectResponse
from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload

from .. import service
from ..db import get_db
from ..models import Child, PlanEntry

router = APIRouter()


@router.get("/roster")
def roster(
    request: Request,
    cls: int | None = None,
    q: str = "",
    db: Session = Depends(get_db),
):
    from ..main import current_teacher, page

    me = current_teacher(request, db)
    if me is None:
        return RedirectResponse("/login", status_code=303)

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
