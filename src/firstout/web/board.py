"""오늘 현황 — 반별 집계와 차수 진행."""

from __future__ import annotations

from fastapi import APIRouter, Depends, Request
from fastapi.responses import RedirectResponse
from sqlalchemy.orm import Session

from .. import service, setup_guide
from ..db import get_db

router = APIRouter()


@router.get("/board")
def board(request: Request, db: Session = Depends(get_db), d: str = ""):
    from ..main import current_user, now, page, pick_date

    me = current_user(request, db)
    if me is None:
        return RedirectResponse("/signin", status_code=303)
    # 운영자는 어느 유치원에도 속하지 않는다. 유치원 화면에 들어오면
    # 빈 목록이 뜨거나 저장하다 터진다 — 운영 화면으로 돌려보낸다.
    if me.kinder_id is None:
        return RedirectResponse("/", status_code=303)

    day, at = pick_date(d), now()
    rows = service.day_rows(db, me.kinder_id, day)
    stats = service.class_stats(db, me.kinder_id, rows)

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


    # 시각이 지났는데 아무도 손대지 않은 아이 — 호출하고 안 오는 것과는 다른 신호다
    for p in progress:
        p["overdue"] = service.overdue(rows, p["round"], at, day)
    total = {
        "total": sum(s.total for s in stats),
        "absent": sum(s.absent for s in stats),
        "early": sum(s.early for s in stats),
        "home": sum(s.home for s in stats),
        "staying": sum(s.staying for s in stats),
    }
    return page(
        request, "board.html", db, me,
        day=day, d=d,
        stats=stats, total=total, progress=progress,
        nocall=service.no_contact(rows),
        overdue=[p for p in progress if p["overdue"]],
        todo=setup_guide.remaining(db, me.kinder_id) if me.is_admin else [],
        weekend=service.weekday_index(day) is None,
    )
