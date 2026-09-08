"""개선 요청 — 「이게 불편해요」를 그 화면에서 바로.

불편한 순간은 그 화면을 보고 있을 때다. 그때 다른 데로 옮겨가서 적으라고 하면
아무도 적지 않고, 적더라도 「명단이 불편해요」처럼 우리가 알아들을 수 없는 말이 된다.

그래서 **모든 화면에 단추를 두고, 어느 화면에서 보냈는지를 자동으로 담는다.**
목록은 따로 둔다 — 보낸 것과 답이 온 것을 한자리에서 보려면 별도 화면이 맞다.
"""

from __future__ import annotations

from fastapi import APIRouter, Depends, Form, Request
from fastapi.responses import RedirectResponse
from sqlalchemy import select
from sqlalchemy.orm import Session

from .. import flash
from ..db import get_db
from ..models import SUG_STATES, Suggestion
from . import clip

router = APIRouter()

MAX_BODY = 1000     # 길게 쓰실 수도 있지만 화면 하나 분량이면 충분하다


@router.post("/suggest")
def send(
    request: Request,
    body: str = Form(""),
    page: str = Form(""),
    db: Session = Depends(get_db),
):
    """어느 화면에서든 보낼 수 있다. 보내고 나면 보던 화면으로 돌아간다."""
    from ..audit import describe
    from ..main import current_user

    me = current_user(request, db)
    if me is None:
        return RedirectResponse("/signin", status_code=303)

    back = page if page.startswith("/") and not page.startswith("//") else "/board"
    text = body.strip()[:MAX_BODY]
    if not text:
        return flash.put(RedirectResponse(back, status_code=303),
                         "무엇이 불편하신지 적어주세요")

    db.add(
        Suggestion(
            kinder_id=me.kinder_id,
            user_id=me.id,
            user_name=me.name,
            kinder_name=me.kinder.name if me.kinder else "",
            # 주소가 아니라 사람이 읽는 화면 이름으로 담는다
            where=clip(describe(back.split("?")[0]), 60),
            body=text,
        )
    )
    db.commit()
    return flash.put(
        RedirectResponse(back, status_code=303),
        "보내주셔서 고맙습니다 — 확인하고 답을 드리겠습니다",
    )


@router.get("/suggest")
def listing(request: Request, db: Session = Depends(get_db)):
    """보낸 것과 답이 온 것. 운영자는 모든 유치원의 것을 본다."""
    from ..main import current_user, page

    me = current_user(request, db)
    if me is None:
        return RedirectResponse("/signin", status_code=303)

    q = select(Suggestion).order_by(Suggestion.created_at.desc())
    if not me.is_operator:
        q = q.where(Suggestion.kinder_id == me.kinder_id)
    rows = list(db.scalars(q.limit(200)))

    return page(
        request, "suggest.html", db, me,
        rows=rows,
        states=SUG_STATES,
        waiting=sum(1 for r in rows if not r.answered),
    )


def _operator(request: Request, db: Session):
    from ..main import current_user

    me = current_user(request, db)
    if me is None:
        return None, RedirectResponse("/signin", status_code=303)
    if not me.is_operator:
        return None, RedirectResponse("/suggest", status_code=303)
    return me, None


@router.post("/suggest/{sid}/reply")
def reply(
    sid: int,
    request: Request,
    reply: str = Form(""),
    status: str = Form(""),
    db: Session = Depends(get_db),
):
    """운영자가 답하고 상태를 정한다. 답이 붙으면 그 유치원 화면에 바로 보인다."""
    from ..main import now

    _, redirect = _operator(request, db)
    if redirect:
        return redirect

    s = db.get(Suggestion, sid)
    if s is None:
        return RedirectResponse("/suggest", status_code=303)

    if reply.strip():
        s.reply = reply.strip()[:MAX_BODY]
        s.replied_at = now()
    if status in SUG_STATES:
        s.status = status
    db.commit()
    return flash.put(RedirectResponse("/suggest", status_code=303),
                     f"{s.kinder_name or '요청'} — 답을 남겼습니다")
