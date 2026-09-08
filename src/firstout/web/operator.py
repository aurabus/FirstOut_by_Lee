"""운영자 화면 — 유치원 가입 승인과 관리.

서비스를 운영하는 우리만 본다. 아무나 가입해서 바로 쓰지 못하도록,
승인을 거쳐야 이용이 시작된다.
"""

from __future__ import annotations

from fastapi import APIRouter, Depends, Form, Request
from fastapi.responses import RedirectResponse
from sqlalchemy import delete, func, select, update
from sqlalchemy.orm import Session

from .. import backup, flash, viewing
from ..config import BACKUP_DIR
from ..db import get_db
from ..models import (
    KG_ACTIVE,
    KG_PENDING,
    KG_SUSPENDED,
    ROLE_ADMIN,
    Academy,
    AuditLog,
    Bus,
    Child,
    ClassRoom,
    Invite,
    Kindergarten,
    Round,
    User,
)
from . import clip

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
    return flash.put(RedirectResponse("/operator", status_code=303), msg)


@router.get("/operator")
def operator_view(request: Request, db: Session = Depends(get_db)):
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
        for u in db.scalars(select(User).where(User.role == ROLE_ADMIN).order_by(User.id))
    }
    last = backup.latest()
    return page(
        request, "operator.html", db, me,
        kinders=kinders, kid_counts=kids, user_counts=users, owners=owners,
        pending=[k for k in kinders if k.status == KG_PENDING],
        backup_last=last,
        backup_kb=(last[1] // 1024) if last else 0,
        backup_dir=str(BACKUP_DIR),
        backup_days=backup.KEEP_DAYS,
        backup_count=len(list(BACKUP_DIR.glob("majung-*.db"))),
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
        k.memo = clip(memo, 200)
        db.commit()
    return _back("메모 저장")


@router.post("/operator/{kid}/reject")
def reject(kid: int, request: Request, db: Session = Depends(get_db)):
    """가입 신청을 지운다 — 장난 신청이 쌓이면 진짜 신청이 묻힌다.

    안전 장치를 두 겹 둔다. **승인대기 상태이면서 원아가 한 명도 없을 때만** 지운다.
    쓰고 있는 유치원이 잘못 눌러 사라지는 일은 어떤 경우에도 없어야 한다.

    감사 로그는 남긴다. 「그런 신청이 있었고 우리가 지웠다」가 기록이기 때문이다.
    """
    _, redirect = _guard(request, db)
    if redirect:
        return redirect

    k = db.get(Kindergarten, kid)
    if k is None:
        return _back()
    if k.status != KG_PENDING:
        return _back(f"{k.name} 은(는) 승인대기 상태가 아니라 지울 수 없습니다")

    kids = db.scalar(select(func.count(Child.id)).where(Child.kinder_id == k.id))
    if kids:
        return _back(f"{k.name} 에 원아 {kids}명이 등록되어 있어 지울 수 없습니다")

    name = k.name
    users = list(db.scalars(select(User).where(User.kinder_id == k.id)))
    uids = [u.id for u in users]

    # 기록은 남기되 사라진 것을 가리키지 않게 한다
    if uids:
        db.execute(delete(Invite).where(Invite.user_id.in_(uids)))
        db.execute(
            update(AuditLog).where(AuditLog.user_id.in_(uids)).values(user_id=None)
        )
    db.execute(update(AuditLog).where(AuditLog.kinder_id == k.id).values(kinder_id=None))

    for model in (Round, Academy, Bus, ClassRoom, User):
        db.execute(delete(model).where(model.kinder_id == k.id))
    db.delete(k)
    db.commit()
    return _back(f"{name} 가입 신청을 지웠습니다")


@router.post("/operator/{kid}/view")
def view_start(kid: int, request: Request, db: Session = Depends(get_db)):
    """그 유치원 화면을 그대로 둘러본다 — 보기 전용.

    「지금 그 원이 어떤 상태인가」를 알려고 매번 계정을 물어보면 원에도 번거롭고
    우리도 느리다. 대신 들어가서 본다. 바꾸는 것은 막힌다(csrf.ViewOnly).
    """
    from ..main import is_secure

    me, redirect = _guard(request, db)
    if redirect:
        return redirect

    k = db.get(Kindergarten, kid)
    if k is None or not k.usable:
        return _back("이용 중인 유치원만 둘러볼 수 있습니다")

    request.state.audit_note = f"{k.name} 둘러보기 시작"
    res = flash.put(RedirectResponse("/board", status_code=303),
                    f"{k.name} 을(를) 둘러보는 중입니다 — 보기 전용")
    return viewing.start(res, k.id, secure=is_secure(request))


@router.post("/view/stop")
def view_stop(request: Request, db: Session = Depends(get_db)):
    """둘러보기를 끝내고 운영 화면으로 돌아온다."""
    from ..main import current_user

    me = current_user(request, db)
    if me is None or not me.is_operator:
        return viewing.stop(RedirectResponse("/", status_code=303))
    request.state.audit_note = f"{me.kinder.name if me.kinder else ''} 둘러보기 끝"
    return viewing.stop(
        flash.put(RedirectResponse("/operator", status_code=303), "둘러보기를 마쳤습니다")
    )
