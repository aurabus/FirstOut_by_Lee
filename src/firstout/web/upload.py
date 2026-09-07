"""원아 명부 엑셀 — 양식 내려받기, 올리기, 확인 후 등록.

명부 관리는 선생님이 주도한다. 우리는 양식을 만들어 주고, 잘못된 줄을 짚어 준다.
**확인을 누르기 전에는 아무것도 저장되지 않는다.** 오타 하나로 150명이 잘못
들어가면 되돌리기 어렵기 때문이다.
"""

from __future__ import annotations

import datetime as dt
import secrets
from urllib.parse import quote

from fastapi import APIRouter, Depends, File, Form, Request, UploadFile
from fastapi.responses import RedirectResponse, Response
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from .. import excel, flash
from ..config import UPLOAD_DIR
from ..db import get_db
from ..models import Child

router = APIRouter()

MAX_BYTES = 5 * 1024 * 1024      # 명부 엑셀이 이보다 클 일은 없다
KEEP_MINUTES = 30                # 올린 파일은 확인용으로만 잠깐 둔다


def _guard(request: Request, db: Session):
    from ..main import current_user

    me = current_user(request, db)
    if me is None:
        return None, RedirectResponse("/signin", status_code=303)
    if not me.is_admin or me.kinder_id is None:
        return None, RedirectResponse("/roster", status_code=303)
    return me, None


def _back(msg: str = "") -> RedirectResponse:
    return flash.put(RedirectResponse("/upload", status_code=303), msg)


def _sweep() -> None:
    """오래된 임시 파일을 치운다 — 원아 정보가 담긴 파일을 남겨두지 않는다."""
    cutoff = dt.datetime.now().timestamp() - KEEP_MINUTES * 60
    for f in UPLOAD_DIR.glob("*.xlsx"):
        try:
            if f.stat().st_mtime < cutoff:
                f.unlink()
        except OSError:
            pass


@router.get("/upload")
def upload_view(request: Request, db: Session = Depends(get_db), token: str = ""):
    from ..main import page

    me, redirect = _guard(request, db)
    if redirect:
        return redirect
    _sweep()

    parsed = None
    if token and _path(token).exists():
        parsed = excel.parse(_path(token).read_bytes(), db, me.kinder_id)

    have = db.scalar(
        select(func.count(Child.id)).where(Child.kinder_id == me.kinder_id, Child.active.is_(True))
    )
    return page(request, "upload.html", db, me, parsed=parsed, token=token, have=have)


@router.get("/upload/template")
def template(request: Request, db: Session = Depends(get_db)):
    """그 유치원의 반·차수·학원이 채워진 빈 양식."""
    me, redirect = _guard(request, db)
    if redirect:
        return redirect

    data = excel.make_template(db, me.kinder_id, me.kinder.name)

    # 헤더는 latin-1 만 담을 수 있어 한글 파일 이름을 그대로 넣으면 500 이 난다.
    # 옛 브라우저용 ASCII 이름과 UTF-8 이름을 함께 보낸다 (RFC 5987).
    name = f"원아명부_양식_{dt.date.today()}.xlsx"
    quoted = quote(name)
    return Response(
        content=data,
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        headers={
            "Content-Disposition":
                f'attachment; filename="majung_roster_{dt.date.today()}.xlsx"; '
                f"filename*=UTF-8''{quoted}"
        },
    )


def _path(token: str):
    safe = "".join(c for c in token if c.isalnum())[:32]
    return UPLOAD_DIR / f"{safe}.xlsx"


@router.post("/upload")
async def upload_file(
    request: Request,
    file: UploadFile = File(...),
    db: Session = Depends(get_db),
):
    """올리기만 하고 저장은 하지 않는다. 다음 화면에서 확인을 받는다."""
    me, redirect = _guard(request, db)
    if redirect:
        return redirect

    data = await file.read()
    if not data:
        return _back("파일이 비어 있습니다")
    if len(data) > MAX_BYTES:
        return _back("파일이 너무 큽니다 (5MB 이하)")
    if not (file.filename or "").lower().endswith((".xlsx", ".xlsm")):
        return _back("엑셀(xlsx) 파일을 올려주세요")

    _sweep()
    token = secrets.token_hex(12)
    _path(token).write_bytes(data)
    return RedirectResponse(f"/upload?token={token}", status_code=303)


@router.post("/upload/apply")
def upload_apply(
    request: Request,
    token: str = Form(""),
    mode: str = Form("add"),
    db: Session = Depends(get_db),
):
    """확인을 누른 뒤에야 저장한다."""
    me, redirect = _guard(request, db)
    if redirect:
        return redirect

    f = _path(token)
    if not token or not f.exists():
        return _back("올린 파일을 찾을 수 없습니다 — 다시 올려주세요")

    made = excel.apply(f.read_bytes(), db, me.kinder_id, replace=(mode == "replace"))
    try:
        f.unlink()   # 원아 정보가 담긴 파일은 바로 지운다
    except OSError:
        pass

    if not made:
        return _back("등록할 수 있는 줄이 없습니다")
    return flash.put(
        RedirectResponse("/roster", status_code=303),
        f"원아 {made}명을 등록했습니다"
        + (" (기존 명부는 지웠습니다)" if mode == "replace" else ""),
    )


@router.post("/upload/cancel")
def upload_cancel(request: Request, token: str = Form(""), db: Session = Depends(get_db)):
    me, redirect = _guard(request, db)
    if redirect:
        return redirect
    f = _path(token)
    if f.exists():
        try:
            f.unlink()
        except OSError:
            pass
    return _back("취소했습니다")
