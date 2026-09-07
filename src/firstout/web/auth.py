"""유치원 선택 → 선생님 선택 → PIN.

한 번 설치해 여러 유치원이 쓰므로, 첫 화면은 유치원을 고르는 자리다.
그다음은 바쁜 하원 시간을 감안해 이름 고르고 네 자리만 누르면 들어간다.
"""

from __future__ import annotations

from fastapi import APIRouter, Depends, Form, Request
from fastapi.responses import RedirectResponse
from sqlalchemy import func, select
from sqlalchemy.orm import Session, selectinload

from .. import service
from ..db import get_db
from ..models import Kindergarten, Teacher
from ..security import make_token, verify_pin
from ..seed import create_kinder

router = APIRouter()


@router.get("/pick")
def pick(request: Request, db: Session = Depends(get_db), msg: str = ""):
    """첫 화면 — 유치원 고르기."""
    from ..main import page

    kinders = service.kindergartens(db)
    counts = dict(
        db.execute(
            select(Teacher.kinder_id, func.count(Teacher.id))
            .where(Teacher.active.is_(True))
            .group_by(Teacher.kinder_id)
        ).all()
    )
    # 한 곳뿐이면 고를 것이 없으니 바로 넘어간다
    if len(kinders) == 1 and not msg:
        return RedirectResponse(f"/login/{kinders[0].id}", status_code=303)

    return page(request, "pick.html", db, None, kinders=kinders, counts=counts, msg=msg)


@router.post("/pick/add")
def pick_add(request: Request, name: str = Form(""), db: Session = Depends(get_db)):
    """새 유치원 등록 — 반·차수·교사 기본값이 함께 만들어진다."""
    name = name.strip()
    if not name:
        return RedirectResponse("/pick?msg=유치원 이름을 입력해 주세요", status_code=303)
    if db.scalar(select(Kindergarten).where(Kindergarten.name == name)):
        return RedirectResponse("/pick?msg=같은 이름의 유치원이 이미 있습니다", status_code=303)

    k = create_kinder(db, name)
    return RedirectResponse(
        f"/login/{k.id}?msg={name} 등록 완료 — 원장으로 들어가 설정을 맞춰주세요", status_code=303
    )


@router.get("/login/{kinder_id}")
def login_form(
    kinder_id: int, request: Request, db: Session = Depends(get_db), error: str = "", msg: str = ""
):
    from ..main import page

    k = db.get(Kindergarten, kinder_id)
    if k is None:
        return RedirectResponse("/pick", status_code=303)

    teachers = list(
        db.scalars(
            select(Teacher)
            .where(Teacher.active.is_(True), Teacher.kinder_id == kinder_id)
            .options(selectinload(Teacher.classroom))
            .order_by(Teacher.is_admin.desc(), Teacher.id)
        )
    )
    return page(
        request, "login.html", db, None,
        kinder=k, teachers=teachers, error=error, msg=msg,
        many=len(service.kindergartens(db)) > 1,
    )


@router.post("/login/{kinder_id}")
def login(
    kinder_id: int,
    request: Request,
    teacher_id: int = Form(...),
    pin: str = Form(""),
    db: Session = Depends(get_db),
):
    t = db.get(Teacher, teacher_id)
    if t is None or t.kinder_id != kinder_id or not verify_pin(pin, t.pin_hash):
        return RedirectResponse(f"/login/{kinder_id}?error=PIN이 맞지 않습니다", status_code=303)

    res = RedirectResponse("/settings" if t.is_admin else "/board", status_code=303)
    res.set_cookie(
        "majung",
        make_token(t.id),
        max_age=60 * 60 * 14,  # 하루 근무 시간 동안 유지
        httponly=True,
        samesite="lax",
    )
    return res


@router.get("/login")
def login_redirect():
    return RedirectResponse("/pick", status_code=303)


@router.post("/logout")
def logout():
    res = RedirectResponse("/pick", status_code=303)
    res.delete_cookie("majung")
    return res
