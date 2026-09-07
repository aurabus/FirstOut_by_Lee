"""오늘 현황 — 반별 집계와 차수 진행."""

from __future__ import annotations

from fastapi import APIRouter, Depends, Request
from fastapi.responses import RedirectResponse
from sqlalchemy.orm import Session

from .. import service
from ..db import get_db

router = APIRouter()


@router.get("/board")
def board(request: Request, db: Session = Depends(get_db), d: str = ""):
    from ..main import current_teacher, now, page, pick_date

    me = current_teacher(request, db)
    if me is None:
        return RedirectResponse("/login", status_code=303)

    day, at = pick_date(d), now()
    rows = service.day_rows(db, me.kinder_id, day)
    stats = service.class_stats(db, me.kinder_id, rows, at)

    progress = []
    for r in service.rounds(db, me.kinder_id):
        target = service.rows_for_round(rows, r)
        progress.append(
            {
                "round": r,
                "total": len(target),
                "done": sum(1 for x in target if x.done),
                "sign": any(x.needs_sign for x in target),
            }
        )

    late = [r for r in rows if r.is_late(at)]
    total = {
        "total": sum(s.total for s in stats),
        "absent": sum(s.absent for s in stats),
        "early": sum(s.early for s in stats),
        "home": sum(s.home for s in stats),
        "staying": sum(s.staying for s in stats),
        "waiting": sum(s.waiting for s in stats),
    }
    return page(
        request, "board.html", db, me,
        day=day, d=d,
        stats=stats, total=total, progress=progress, late=late,
        weekend=service.weekday_index(day) is None,
    )
