"""사용 안내 — 프로그램 안에서 바로 찾아보는 매뉴얼.

궁금한 것이 생기는 때는 화면을 보고 있을 때다. 그때 종이나 카카오톡을 뒤지게 하면
아무도 보지 않는다. 그래서 서버에 함께 담아 두고, 각 화면에서 그 대목으로 바로 간다.

바깥 자원을 쓰지 않는다 — 글꼴도 그림도 서버 안에 있으므로 인터넷이 끊겨도 열린다.
"""

from __future__ import annotations

from fastapi import APIRouter, Depends, Request
from fastapi.responses import RedirectResponse
from sqlalchemy.orm import Session

from ..db import get_db

router = APIRouter()


@router.get("/help")
def help_page(request: Request, db: Session = Depends(get_db)):
    """로그인한 사람이면 누구나 본다. 관리자용 대목은 화면에서 표시만 다르게 한다."""
    from ..main import current_user, page

    me = current_user(request, db)
    if me is None:
        return RedirectResponse("/signin", status_code=303)
    return page(request, "help.html", db, me)
