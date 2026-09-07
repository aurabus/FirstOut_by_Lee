"""선생님 계정 관리 — 유치원이 직접 한다.

우리가 계정을 만들어 주면 사람이 바뀔 때마다 연락이 와야 한다.
총괄 관리자가 스스로 추가·수정·정지할 수 있어야 서비스가 굴러간다.
시작하는 사람이 늘 원장인 것은 아니라 권한 이름은 「총괄 관리자」로 둔다.
"""

from __future__ import annotations

import secrets

from fastapi import APIRouter, Depends, Form, Request
from fastapi.responses import RedirectResponse
from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload

from .. import flash, invites, net, reauth, service
from ..db import get_db
from ..models import ADMIN_TITLES, ROLE_ADMIN, ROLE_TEACHER, TITLES, User
from ..security import hash_password
from . import clip

router = APIRouter()


def _guard(request: Request, db: Session):
    from ..main import current_user

    me = current_user(request, db)
    if me is None:
        return None, RedirectResponse("/signin", status_code=303)
    if not me.is_admin:
        return None, RedirectResponse("/board", status_code=303)
    # 운영자는 어느 유치원에도 속하지 않는다. 유치원 화면에 들어오면
    # 빈 목록이 뜨거나 저장하다 터진다 — 운영 화면으로 돌려보낸다.
    if me.kinder_id is None:
        return None, RedirectResponse("/", status_code=303)
    if wall := reauth.wall(request, me, back="/users"):   # 계정을 만들고 지우는 화면이다
        return None, wall
    return me, None


def _back(msg: str = "", secret: str = "") -> RedirectResponse:
    """안내문은 쿠키로 넘긴다 — 임시 비밀번호가 주소에 남으면 안 된다."""
    return flash.put(RedirectResponse("/users", status_code=303), msg, secret)


def temp_password() -> str:
    """초대 QR 을 못 쓸 때의 대비책. 첫 로그인 때 바꾸게 한다.

    카카오톡·문자로 오가는 값이라 넉넉히 넓힌다. 네 자리면 만 가지도 안 된다.
    """
    return "majung" + f"{secrets.randbelow(1_000_000):06d}"


@router.get("/users")
def users_view(request: Request, db: Session = Depends(get_db)):
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
        users=users,
        classes=service.classes(db, me.kinder_id),
        titles=TITLES,
        admin_titles=ADMIN_TITLES,
        role_admin=ROLE_ADMIN,
        role_teacher=ROLE_TEACHER,
    )


@router.post("/users/add")
def user_add(
    request: Request,
    name: str = Form(""),
    login_id: str = Form(""),
    title: str = Form(""),
    title_other: str = Form(""),
    class_id: str = Form(""),
    role: str = Form(ROLE_TEACHER),
    db: Session = Depends(get_db),
):
    me, redirect = _guard(request, db)
    if redirect:
        return redirect

    name = clip(name, 40)
    login_id = login_id.strip().lower()[:30]
    if not name or not login_id:
        return _back("이름과 아이디를 입력해 주세요")
    if len(login_id) < 4 or not login_id.replace("_", "").isalnum():
        return _back("아이디는 영문·숫자 4자 이상으로 정해주세요")
    if db.scalar(select(User).where(User.login_id == login_id)):
        return _back("이미 쓰이고 있는 아이디입니다")

    # 직함은 유치원마다 부르는 말이 달라 직접 적을 수도 있다
    job = clip(title_other, 20) if title == "기타" else clip(title, 20)

    # 비밀번호는 아무도 모르는 값으로 둔다. 들어오는 길은 초대 QR 하나뿐이고,
    # 그것을 못 쓰면 관리자가 「비밀번호 재발급」을 누르면 된다.
    u = User(
        kinder_id=me.kinder_id,
        login_id=login_id,
        password_hash=hash_password(secrets.token_urlsafe(32)),
        name=name,
        role=ROLE_ADMIN if role == ROLE_ADMIN else ROLE_TEACHER,
        title=job,
        class_id=int(class_id) if class_id.isdigit() else None,
        must_change_pw=True,   # 첫 로그인 때 본인이 정하게 한다
    )
    db.add(u)
    db.commit()
    return _invite_now(db, me, u, f"{name} 선생님 계정을 만들었습니다")


def _invite_now(db: Session, me: User, u: User, msg: str) -> RedirectResponse:
    """초대를 만들고, 원문은 쿠키로만 넘긴다 — 주소에 실으면 기록에 남는다."""
    from ..main import now

    token = invites.issue(db, u, me, now())
    return flash.put(
        RedirectResponse(f"/users/{u.id}/invite", status_code=303), msg, token
    )


@router.post("/users/{uid}/invite")
def user_invite(uid: int, request: Request, db: Session = Depends(get_db)):
    """초대를 다시 만든다 — 10분이 지났거나 잘못 찍었을 때."""
    me, redirect = _guard(request, db)
    if redirect:
        return redirect
    u = db.get(User, uid)
    if u is None or u.kinder_id != me.kinder_id:
        return _back()
    if u.id == me.id:
        # 초대를 쓰면 비밀번호가 새로 정해진다. 본인 것은 비밀번호 화면에서 바꾼다.
        return _back("본인 비밀번호는 위쪽 「비밀번호」 에서 바꿔주세요")
    return _invite_now(db, me, u, f"{u.name} 선생님 초대를 새로 만들었습니다")


@router.get("/users/{uid}/invite")
def user_invite_view(uid: int, request: Request, db: Session = Depends(get_db)):
    """관리자가 화면을 선생님 휴대폰 쪽으로 돌려 보여주는 화면.

    초대 원문은 방금 만들어 준 쿠키에만 있다. 새로고침하면 사라지므로
    다시 만들도록 안내한다 — 그래야 화면에 오래 떠 있지 않는다.
    """
    from ..main import page

    me, redirect = _guard(request, db)
    if redirect:
        return redirect
    u = db.get(User, uid)
    if u is None or u.kinder_id != me.kinder_id:
        return _back()

    _, token = flash.take(request)
    url = invites.link(token, request) if token else ""
    return page(
        request, "invite.html", db, me,
        who=u,
        url=url,
        qr=net.qr_svg(url) if url else "",
        minutes=invites.MINUTES,
    )


@router.post("/users/{uid}/save")
def user_save(
    uid: int,
    request: Request,
    name: str = Form(""),
    title: str = Form(""),
    class_id: str = Form(""),
    role: str = Form(""),
    db: Session = Depends(get_db),
):
    me, redirect = _guard(request, db)
    if redirect:
        return redirect
    u = db.get(User, uid)
    if u is None or u.kinder_id != me.kinder_id:
        return _back()
    if name.strip():
        u.name = clip(name, 40)
    u.title = clip(title, 20)
    if role in (ROLE_ADMIN, ROLE_TEACHER) and u.id != me.id:
        # 본인 권한은 못 내린다 — 마지막 관리자가 스스로 문을 잠그면 아무도 못 연다
        if u.role == ROLE_ADMIN and role == ROLE_TEACHER and _admin_count(db, me.kinder_id) < 2:
            return _back("관리자가 한 분뿐이라 권한을 내릴 수 없습니다")
        if u.role != role:
            request.state.audit_note = f"{u.name} 권한 {u.role} → {role}"
        u.role = role
    u.class_id = int(class_id) if class_id.isdigit() else None
    db.commit()
    return _back(f"{u.name} 선생님 정보 저장")


@router.post("/users/{uid}/reset")
def user_reset(uid: int, request: Request, db: Session = Depends(get_db)):
    """비밀번호를 잊었을 때. 관리자도 남의 비밀번호를 볼 수는 없고, 새로 발급만 한다."""
    me, redirect = _guard(request, db)
    if redirect:
        return redirect
    u = db.get(User, uid)
    if u is None or u.kinder_id != me.kinder_id:
        return _back()
    if u.id == me.id:
        # 스스로 발급하면 그 자리에서 로그인이 끊긴다. 본인은 비밀번호 화면에서 바꾼다.
        return _back("본인 비밀번호는 위쪽 「비밀번호」 에서 바꿔주세요")

    pw = temp_password()
    u.password_hash = hash_password(pw)
    u.must_change_pw = True
    u.failed_count = 0
    u.locked_until = None
    db.commit()
    return _back(f"{u.name} 선생님 비밀번호를 새로 발급했습니다", f"{u.login_id} / {pw}")


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
    if u.role == ROLE_ADMIN and _admin_count(db, me.kinder_id) < 2:
        return _back("관리자가 한 분뿐이라 멈출 수 없습니다")

    u.active = not u.active
    request.state.audit_note = f"{u.name} 계정 {'사용' if u.active else '중지'}"
    db.commit()
    return _back(f"{u.name} 선생님 — {'사용' if u.active else '중지'}")


def _admin_count(db: Session, kinder_id: int) -> int:
    return len(
        list(
            db.scalars(
                select(User).where(
                    User.kinder_id == kinder_id,
                    User.role == ROLE_ADMIN,
                    User.active.is_(True),
                )
            )
        )
    )
