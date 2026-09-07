"""선생님 계정 관리 — 원장이 직접 한다.

우리가 계정을 만들어 주면 사람이 바뀔 때마다 연락이 와야 한다.
원장이 스스로 추가·수정·정지할 수 있어야 서비스가 굴러간다.
"""

from __future__ import annotations

import secrets

from fastapi import APIRouter, Depends, Form, Request
from fastapi.responses import RedirectResponse
from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload

from .. import service
from ..db import get_db
from ..models import ROLE_OWNER, ROLE_TEACHER, User
from ..security import hash_password

router = APIRouter()


def _guard(request: Request, db: Session):
    from ..main import current_user

    me = current_user(request, db)
    if me is None:
        return None, RedirectResponse("/signin", status_code=303)
    if not me.is_admin or me.kinder_id is None:
        return None, RedirectResponse("/board", status_code=303)
    return me, None


def _back(msg: str = "") -> RedirectResponse:
    return RedirectResponse(f"/users?msg={msg}", status_code=303)


def temp_password() -> str:
    """원장이 선생님께 전달할 임시 비밀번호. 첫 로그인 때 바꾸게 한다."""
    return "majung" + str(secrets.randbelow(9000) + 1000)


@router.get("/users")
def users_view(request: Request, db: Session = Depends(get_db), msg: str = "", pw: str = ""):
    from ..main import page

    me, redirect = _guard(request, db)
    if redirect:
        return redirect

    users = list(
        db.scalars(
            select(User)
            .where(User.kinder_id == me.kinder_id)
            .options(selectinload(User.classroom))
            .order_by(User.role, User.id)
        )
    )
    return page(
        request, "users.html", db, me,
        users=users, msg=msg, new_pw=pw,
        classes=service.classes(db, me.kinder_id),
    )


@router.post("/users/add")
def user_add(
    request: Request,
    name: str = Form(""),
    login_id: str = Form(""),
    title: str = Form(""),
    class_id: str = Form(""),
    role: str = Form(ROLE_TEACHER),
    db: Session = Depends(get_db),
):
    me, redirect = _guard(request, db)
    if redirect:
        return redirect

    name = name.strip()
    login_id = login_id.strip().lower()
    if not name or not login_id:
        return _back("이름과 아이디를 입력해 주세요")
    if len(login_id) < 4 or not login_id.replace("_", "").isalnum():
        return _back("아이디는 영문·숫자 4자 이상으로 정해주세요")
    if db.scalar(select(User).where(User.login_id == login_id)):
        return _back("이미 쓰이고 있는 아이디입니다")

    pw = temp_password()
    db.add(
        User(
            kinder_id=me.kinder_id,
            login_id=login_id,
            password_hash=hash_password(pw),
            name=name,
            role=ROLE_OWNER if role == ROLE_OWNER else ROLE_TEACHER,
            title=title.strip(),
            class_id=int(class_id) if class_id.isdigit() else None,
            must_change_pw=True,   # 첫 로그인 때 본인이 정하게 한다
        )
    )
    db.commit()
    return RedirectResponse(
        f"/users?msg={name} 선생님 계정을 만들었습니다&pw={login_id} / {pw}", status_code=303
    )


@router.post("/users/{uid}/save")
def user_save(
    uid: int,
    request: Request,
    name: str = Form(""),
    title: str = Form(""),
    class_id: str = Form(""),
    db: Session = Depends(get_db),
):
    me, redirect = _guard(request, db)
    if redirect:
        return redirect
    u = db.get(User, uid)
    if u is None or u.kinder_id != me.kinder_id:
        return _back()
    if name.strip():
        u.name = name.strip()
    u.title = title.strip()
    u.class_id = int(class_id) if class_id.isdigit() else None
    db.commit()
    return _back(f"{u.name} 선생님 정보 저장")


@router.post("/users/{uid}/reset")
def user_reset(uid: int, request: Request, db: Session = Depends(get_db)):
    """비밀번호를 잊었을 때. 원장도 남의 비밀번호를 볼 수는 없고, 새로 발급만 한다."""
    me, redirect = _guard(request, db)
    if redirect:
        return redirect
    u = db.get(User, uid)
    if u is None or u.kinder_id != me.kinder_id:
        return _back()

    pw = temp_password()
    u.password_hash = hash_password(pw)
    u.must_change_pw = True
    u.failed_count = 0
    u.locked_until = None
    db.commit()
    return RedirectResponse(
        f"/users?msg={u.name} 선생님 비밀번호를 새로 발급했습니다&pw={u.login_id} / {pw}",
        status_code=303,
    )


@router.post("/users/{uid}/toggle")
def user_toggle(uid: int, request: Request, db: Session = Depends(get_db)):
    """그만두신 선생님은 지우지 않고 멈춘다. 지난 인계 기록의 처리자가 사라지면 안 된다."""
    me, redirect = _guard(request, db)
    if redirect:
        return redirect
    u = db.get(User, uid)
    if u is None or u.kinder_id != me.kinder_id:
        return _back()
    if u.id == me.id:
        return _back("본인 계정은 멈출 수 없습니다")
    if u.role == ROLE_OWNER and _owner_count(db, me.kinder_id) < 2:
        return _back("원장 계정이 하나뿐이라 멈출 수 없습니다")

    u.active = not u.active
    db.commit()
    return _back(f"{u.name} 선생님 — {'사용' if u.active else '중지'}")


def _owner_count(db: Session, kinder_id: int) -> int:
    return len(
        list(
            db.scalars(
                select(User).where(
                    User.kinder_id == kinder_id,
                    User.role == ROLE_OWNER,
                    User.active.is_(True),
                )
            )
        )
    )
