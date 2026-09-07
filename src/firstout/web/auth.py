"""가입 · 로그인 · 비밀번호.

원장만 가입을 신청하고 운영자가 승인한다. 교사 계정은 원장이 만든다.
아이디 하나로 어느 유치원 사람인지 정해지므로, 유치원 목록도 선생님 명단도
로그인 전에는 드러나지 않는다.
"""

from __future__ import annotations

import datetime as dt

from fastapi import APIRouter, Depends, Form, Request
from fastapi.responses import RedirectResponse
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from .. import flash
from ..db import get_db
from ..models import (
    KG_ACTIVE,
    KG_PENDING,
    ROLE_OWNER,
    Kindergarten,
    User,
)
from ..security import (
    SESSION_MAX_AGE,
    hash_password,
    make_token,
    password_problem,
    verify_password,
)
from ..seed import fill_new_kinder

router = APIRouter()

LOCK_AFTER = 5              # 이만큼 틀리면 잠근다
LOCK_MINUTES = 10           # 자동 대입을 막을 만큼만 — 선생님이 오래 못 쓰면 안 된다


def _set_session(res: RedirectResponse, user: User, secure: bool) -> None:
    res.set_cookie(
        "majung",
        make_token(user.id, user.password_hash),
        max_age=SESSION_MAX_AGE,
        httponly=True,
        samesite="lax",
        secure=secure,
    )


# ── 로그인 ──────────────────────────────────────────────

@router.get("/signin")
def signin_form(request: Request, db: Session = Depends(get_db), error: str = "", msg: str = ""):
    from ..main import current_user, page

    if current_user(request, db):
        return RedirectResponse("/", status_code=303)
    return page(request, "signin.html", db, None, error=error, msg=msg)


@router.post("/signin")
def signin(
    request: Request,
    login_id: str = Form(""),
    password: str = Form(""),
    db: Session = Depends(get_db),
):
    from ..main import now

    u = db.scalar(select(User).where(User.login_id == login_id.strip().lower()))
    at = now()

    # 아이디가 없든 비밀번호가 틀리든 같은 문구를 보여준다.
    # 어느 아이디가 실제로 있는지 알려주지 않기 위해서다.
    fail = "/signin?error=아이디 또는 비밀번호가 맞지 않습니다"

    if u is None or not u.active:
        return RedirectResponse(fail, status_code=303)

    if u.locked_until and u.locked_until > at:
        left = int((u.locked_until - at).total_seconds() // 60) + 1
        return RedirectResponse(
            f"/signin?error=여러 번 틀려 잠겼습니다 — {left}분 후 다시 시도해 주세요",
            status_code=303,
        )

    if not verify_password(password, u.password_hash):
        u.failed_count += 1
        if u.failed_count >= LOCK_AFTER:
            u.locked_until = at + dt.timedelta(minutes=LOCK_MINUTES)
            u.failed_count = 0
        db.commit()
        return RedirectResponse(fail, status_code=303)

    if u.kinder and u.kinder.status == KG_PENDING:
        return RedirectResponse(
            "/signin?msg=가입 신청이 접수되었습니다 — 승인 후 이용하실 수 있습니다",
            status_code=303,
        )
    if u.kinder and not u.kinder.usable:
        return RedirectResponse("/signin?error=이용이 중지된 유치원입니다", status_code=303)

    u.failed_count = 0
    u.locked_until = None
    u.last_login_at = at
    db.commit()

    dest = "/me/password" if u.must_change_pw else "/"
    res = RedirectResponse(dest, status_code=303)
    from ..main import is_secure

    _set_session(res, u, secure=is_secure(request))
    return res


@router.post("/signout")
def signout():
    res = RedirectResponse("/signin", status_code=303)
    res.delete_cookie("majung")
    return res


# ── 유치원 가입 신청 ────────────────────────────────────

@router.get("/signup")
def signup_form(request: Request, db: Session = Depends(get_db), error: str = "", form: str = ""):
    from ..main import page

    return page(request, "signup.html", db, None, error=error, form=form)


@router.post("/signup")
def signup(
    request: Request,
    kinder_name: str = Form(""),
    phone: str = Form(""),
    name: str = Form(""),
    login_id: str = Form(""),
    email: str = Form(""),
    password: str = Form(""),
    password2: str = Form(""),
    db: Session = Depends(get_db),
):
    """원장이 유치원과 자기 계정을 함께 신청한다."""
    kinder_name = kinder_name.strip()
    login_id = login_id.strip().lower()
    name = name.strip()

    def back(msg: str) -> RedirectResponse:
        return RedirectResponse(f"/signup?error={msg}", status_code=303)

    if not (kinder_name and name and login_id):
        return back("유치원 이름 · 원장님 성함 · 아이디를 모두 입력해 주세요")
    if len(login_id) < 4 or not login_id.replace("_", "").isalnum():
        return back("아이디는 영문·숫자 4자 이상으로 정해주세요")
    if password != password2:
        return back("비밀번호가 서로 다릅니다")
    if bad := password_problem(password):
        return back(bad)
    if db.scalar(select(User).where(User.login_id == login_id)):
        return back("이미 쓰이고 있는 아이디입니다")
    if db.scalar(select(Kindergarten).where(Kindergarten.name == kinder_name)):
        return back("이미 등록된 유치원입니다 — 원장님께 계정을 요청해 주세요")

    k = Kindergarten(
        name=kinder_name,
        phone=phone.strip(),
        status=KG_PENDING,
        seq=(db.scalar(select(func.max(Kindergarten.seq))) or 0) + 1,
    )
    db.add(k)
    db.flush()
    fill_new_kinder(db, k)   # 반·차수·학원 기본값 — 승인 뒤 바로 쓸 수 있게

    db.add(
        User(
            kinder_id=k.id,
            login_id=login_id,
            password_hash=hash_password(password),
            name=name,
            role=ROLE_OWNER,
            title="원장",
            email=email.strip(),
            phone=phone.strip(),
        )
    )
    db.commit()
    return RedirectResponse("/signup/done", status_code=303)


@router.get("/signup/done")
def signup_done(request: Request, db: Session = Depends(get_db)):
    from ..main import page

    return page(request, "signup_done.html", db, None)


# ── 비밀번호 변경 ───────────────────────────────────────

@router.get("/me/password")
def password_form(request: Request, db: Session = Depends(get_db), error: str = "", msg: str = ""):
    from ..main import current_user, page

    me = current_user(request, db)
    if me is None:
        return RedirectResponse("/signin", status_code=303)
    return page(request, "password.html", db, me, error=error, msg=msg)


@router.post("/me/password")
def password_change(
    request: Request,
    current: str = Form(""),
    password: str = Form(""),
    password2: str = Form(""),
    db: Session = Depends(get_db),
):
    from ..main import current_user

    me = current_user(request, db)
    if me is None:
        return RedirectResponse("/signin", status_code=303)

    def back(msg: str) -> RedirectResponse:
        return RedirectResponse(f"/me/password?error={msg}", status_code=303)

    # 처음 받은 비밀번호를 바꾸는 중이라면 현재 비밀번호를 다시 묻지 않는다
    if not me.must_change_pw and not verify_password(current, me.password_hash):
        return back("현재 비밀번호가 맞지 않습니다")
    if password != password2:
        return back("새 비밀번호가 서로 다릅니다")
    if bad := password_problem(password):
        return back(bad)
    if verify_password(password, me.password_hash):
        return back("지금 쓰는 비밀번호와 같습니다")

    me.password_hash = hash_password(password)
    me.must_change_pw = False
    db.commit()

    # 다른 기기에 남아 있던 로그인은 모두 끊기므로, 이 기기만 새로 이어준다
    from ..main import is_secure

    res = flash.put(RedirectResponse("/", status_code=303),
                    "비밀번호를 바꿨습니다 — 다른 기기의 로그인은 모두 해제되었습니다")
    _set_session(res, me, secure=is_secure(request))
    return res


# 예전 주소를 눌러도 헤매지 않게
@router.get("/login")
def login_redirect():
    return RedirectResponse("/signin", status_code=303)


@router.get("/pick")
def pick_redirect():
    return RedirectResponse("/signin", status_code=303)


__all__ = ["router", "KG_ACTIVE"]
