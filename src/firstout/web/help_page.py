"""사용 안내 — 프로그램 안에서 바로 찾아보는 매뉴얼.

궁금한 것이 생기는 때는 화면을 보고 있을 때다. 그때 종이나 카카오톡을 뒤지게 하면
아무도 보지 않는다. 그래서 서버에 함께 담아 두고, 각 화면에서 그 대목으로 바로 간다.

**로그인 전에도 열린다.** 선생님이 이 프로그램을 처음 만나는 자리가 로그인 화면인데,
거기서 안내를 못 보면 「뭘 하는 건지」 모른 채 아이디부터 받게 된다. 담긴 것은
쓰는 방법뿐이고 아이 이름도 원 이름도 없으니, 열어 두어도 잃을 것이 없다.

바깥 자원을 쓰지 않는다 — 글꼴도 그림도 서버 안에 있으므로 인터넷이 끊겨도 열린다.
"""

from __future__ import annotations

from types import SimpleNamespace

from fastapi import APIRouter, Depends, Request
from sqlalchemy.orm import Session

from ..db import get_db
from ..seed import DEFAULT_ROUNDS

router = APIRouter()


def _보기용_차수() -> list[SimpleNamespace]:
    """아직 어느 원인지 모를 때 보여줄 차수.

    빈 표를 보여주고 「설정에서 정해주세요」라고 하면, 로그인도 안 한 사람에게
    할 수 없는 일을 시키는 말이 된다. 새 유치원에 처음 깔리는 그 값을 그대로 쓴다.
    """
    return [
        SimpleNamespace(at_time=at, name=이름, note=비고, needs_sign=서명)
        for _키, 이름, _종류, at, 비고, 서명 in DEFAULT_ROUNDS
    ]


@router.get("/help")
def help_page(request: Request, db: Session = Depends(get_db)):
    """로그인한 사람은 자기 원의 차수로, 아직 안 한 사람은 기본값으로 본다."""
    from ..main import current_user, page

    me = current_user(request, db)
    if me is None:
        return page(request, "help.html", db, None,
                    rounds=_보기용_차수(), 공개=True)
    return page(request, "help.html", db, me)
