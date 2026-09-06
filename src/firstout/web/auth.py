"""PIN 로그인.

선생님 이름을 고르고 네 자리만 누르면 들어간다.
바쁜 하원 시간에 아이디·비밀번호를 칠 수는 없기 때문이다.
"""

from __future__ import annotations

from fastapi import APIRouter, Depends, Form, Request
from fastapi.responses import RedirectResponse
from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload

from ..db import get_db
from ..models import Teacher
from ..security import make_token, verify_pin

router = APIRouter()


@router.get("/login")
def login_form(request: Request, db: Session = Depends(get_db), error: str = ""):
    from ..main import page

    teachers = list(
        db.scalars(
            select(Teacher)
            .where(Teacher.active.is_(True))
            .options(selectinload(Teacher.classroom))
            .order_by(Teacher.is_admin.desc(), Teacher.id)
        )
    )
    return page(request, "login.html", db, None, teachers=teachers, error=error)


@router.post("/login")
def login(
    request: Request,
    teacher_id: int = Form(...),
    pin: str = Form(""),
    db: Session = Depends(get_db),
):
    t = db.get(Teacher, teacher_id)
    if t is None or not verify_pin(pin, t.pin_hash):
        return RedirectResponse("/login?error=PIN이 맞지 않습니다", status_code=303)

    dest = "/settings" if t.is_admin else "/board"
    res = RedirectResponse(dest, status_code=303)
    res.set_cookie(
        "majung",
        make_token(t.id),
        max_age=60 * 60 * 14,  # 하루 근무 시간 동안 유지
        httponly=True,
        samesite="lax",
    )
    return res


@router.post("/logout")
def logout():
    res = RedirectResponse("/login", status_code=303)
    res.delete_cookie("majung")
    return res
