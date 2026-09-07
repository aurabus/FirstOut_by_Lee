"""운영자 화면 — 유치원 가입 승인과 관리.

서비스를 운영하는 우리만 본다. 아무나 가입해서 바로 쓰지 못하도록,
승인을 거쳐야 이용이 시작된다.
"""

from __future__ import annotations

from fastapi import APIRouter, Depends, Form, Request
from fastapi.responses import RedirectResponse
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from ..db import get_db
from ..models import (
    KG_ACTIVE,
    KG_PENDING,
    KG_SUSPENDED,
    Child,
    Kindergarten,
    User,
)

router = APIRouter()


def _guard(request: Request, db: Session):
    from ..main import current_user

    me = current_user(request, db)
    if me is None:
        return None, RedirectResponse("/signin", status_code=303)
    if not me.is_operator:
        return None, RedirectResponse("/board", status_code=303)
    return me, None


def _back(msg: str = "") -> RedirectResponse:
    return RedirectResponse(f"/operator?msg={msg}", status_code=303)


@router.get("/operator")
def operator_view(request: Request, db: Session = Depends(get_db), msg: str = ""):
    from ..main import page

    me, redirect = _guard(request, db)
    if redirect:
        return redirect

    kinders = list(db.scalars(select(Kindergarten).order_by(Kindergarten.created_at.desc())))
    kids = dict(
        db.execute(
            select(Child.kinder_id, func.count(Child.id))
            .where(Child.active.is_(True))
            .group_by(Child.kinder_id)
        ).all()
    )
    users = dict(
        db.execute(
            select(User.kinder_id, func.count(User.id))
            .where(User.active.is_(True))
            .group_by(User.kinder_id)
        ).all()
    )
    owners = {
        u.kinder_id: u
        for u in db.scalars(select(User).where(User.role == "원장").order_by(User.id))
    }
    return page(
        request, "operator.html", db, me,
        kinders=kinders, kid_counts=kids, user_counts=users, owners=owners,
        pending=[k for k in kinders if k.status == KG_PENDING],
        msg=msg,
    )


@router.post("/operator/{kid}/approve")
def approve(kid: int, request: Request, db: Session = Depends(get_db)):
    from ..main import now

    _, redirect = _guard(request, db)
    if redirect:
        return redirect
    k = db.get(Kindergarten, kid)
    if k:
        k.status = KG_ACTIVE
        k.approved_at = now()
        db.commit()
        return _back(f"{k.name} 승인 — 이제 이용하실 수 있습니다")
    return _back()


@router.post("/operator/{kid}/suspend")
def suspend(kid: int, request: Request, db: Session = Depends(get_db)):
    _, redirect = _guard(request, db)
    if redirect:
        return redirect
    k = db.get(Kindergarten, kid)
    if k:
        k.status = KG_SUSPENDED
        db.commit()
        return _back(f"{k.name} 이용 중지")
    return _back()


@router.post("/operator/{kid}/memo")
def memo(kid: int, request: Request, memo: str = Form(""), db: Session = Depends(get_db)):
    _, redirect = _guard(request, db)
    if redirect:
        return redirect
    k = db.get(Kindergarten, kid)
    if k:
        k.memo = memo.strip()
        db.commit()
    return _back("메모 저장")
