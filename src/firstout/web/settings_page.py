"""관리자 설정 — 반·차량·차수·학원.

이 프로그램은 한 유치원 전용이 아니다. 원마다 다른 값은 전부 여기서 맞춘다.
"""

from __future__ import annotations

from fastapi import APIRouter, Depends, Form, Request
from fastapi.responses import RedirectResponse
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from .. import service
from ..db import get_db
from ..models import Academy, Bus, Child, ClassRoom, Kindergarten, PlanEntry, Round

router = APIRouter()


def _guard(request: Request, db: Session):
    from ..main import current_teacher

    me = current_teacher(request, db)
    if me is None:
        return None, RedirectResponse("/login", status_code=303)
    if not me.is_admin:
        return None, RedirectResponse("/board", status_code=303)
    return me, None


@router.get("/settings")
def settings_view(request: Request, db: Session = Depends(get_db), msg: str = ""):
    from ..main import page

    me, redirect = _guard(request, db)
    if redirect:
        return redirect

    counts = dict(
        db.execute(
            select(Child.class_id, func.count(Child.id))
            .where(Child.kinder_id == me.kinder_id)
            .group_by(Child.class_id)
        ).all()
    )
    buses = list(
        db.scalars(select(Bus).where(Bus.kinder_id == me.kinder_id).order_by(Bus.seq, Bus.id))
    )
    academies = list(
        db.scalars(select(Academy).where(Academy.kinder_id == me.kinder_id).order_by(Academy.name))
    )
    return page(
        request, "settings.html", db, me,
        counts=counts, buses=buses, academies=academies, msg=msg,
    )


def _back(msg: str = "") -> RedirectResponse:
    return RedirectResponse(f"/settings?msg={msg}", status_code=303)


# ── 반 ──────────────────────────────────────────────────

@router.post("/settings/class/add")
def class_add(request: Request, name: str = Form(""), db: Session = Depends(get_db)):
    me, redirect = _guard(request, db)
    if redirect:
        return redirect
    n = db.scalar(select(func.count(ClassRoom.id)).where(ClassRoom.kinder_id == me.kinder_id))
    name = name.strip() or f"새 반 {n + 1}"
    if db.scalar(
        select(ClassRoom).where(ClassRoom.kinder_id == me.kinder_id, ClassRoom.name == name)
    ):
        return _back("같은 이름의 반이 이미 있습니다")
    top = db.scalar(select(func.max(ClassRoom.seq)).where(ClassRoom.kinder_id == me.kinder_id))
    seq = (top or 0) + 1
    db.add(ClassRoom(kinder_id=me.kinder_id, name=name, seq=seq))
    db.commit()
    return _back(f"{name} 추가")


@router.post("/settings/class/{cid}/rename")
def class_rename(cid: int, request: Request, name: str = Form(""), db: Session = Depends(get_db)):
    _, redirect = _guard(request, db)
    if redirect:
        return redirect
    c = db.get(ClassRoom, cid)
    if c and name.strip():
        c.name = name.strip()
        db.commit()
    return _back("반 이름 변경")


@router.post("/settings/class/{cid}/move")
def class_move(cid: int, request: Request, dir: int = Form(0), db: Session = Depends(get_db)):
    """동선 순서를 바꾼다 — 모든 명단 정렬이 이 순서를 따른다."""
    me, redirect = _guard(request, db)
    if redirect:
        return redirect
    rooms = service.classes(db, me.kinder_id)
    idx = next((i for i, r in enumerate(rooms) if r.id == cid), None)
    if idx is not None:
        j = idx + (1 if dir > 0 else -1)
        if 0 <= j < len(rooms):
            rooms[idx].seq, rooms[j].seq = rooms[j].seq, rooms[idx].seq
            db.commit()
    return _back("순서 변경")


@router.post("/settings/class/{cid}/delete")
def class_delete(cid: int, request: Request, db: Session = Depends(get_db)):
    _, redirect = _guard(request, db)
    if redirect:
        return redirect
    if db.scalar(select(func.count(Child.id)).where(Child.class_id == cid)):
        return _back("원아가 있는 반은 삭제할 수 없습니다")
    c = db.get(ClassRoom, cid)
    if c:
        db.delete(c)
        db.commit()
    return _back("반 삭제")


# ── 차량 ────────────────────────────────────────────────

@router.post("/settings/bus/add")
def bus_add(request: Request, db: Session = Depends(get_db)):
    me, redirect = _guard(request, db)
    if redirect:
        return redirect
    n = db.scalar(select(func.count(Bus.id)).where(Bus.kinder_id == me.kinder_id)) + 1
    db.add(Bus(kinder_id=me.kinder_id, name=f"차량 {n}호", seq=n))
    db.commit()
    return _back("차량 추가 — 명단이 차량별로 나뉩니다")


@router.post("/settings/bus/{bid}/rename")
def bus_rename(bid: int, request: Request, name: str = Form(""), db: Session = Depends(get_db)):
    _, redirect = _guard(request, db)
    if redirect:
        return redirect
    b = db.get(Bus, bid)
    if b and name.strip():
        b.name = name.strip()
        db.commit()
    return _back("차량 이름 변경")


@router.post("/settings/bus/{bid}/delete")
def bus_delete(bid: int, request: Request, db: Session = Depends(get_db)):
    me, redirect = _guard(request, db)
    if redirect:
        return redirect
    if db.scalar(select(func.count(Bus.id)).where(Bus.kinder_id == me.kinder_id)) < 2:
        return _back("차량은 최소 한 대가 필요합니다")
    if db.scalar(select(func.count(Round.id)).where(Round.bus_id == bid)):
        return _back("이 차량을 쓰는 차수가 있어 삭제할 수 없습니다")
    b = db.get(Bus, bid)
    if b:
        db.delete(b)
        db.commit()
    return _back("차량 삭제")


# ── 차수 ────────────────────────────────────────────────

@router.post("/settings/round/{rid}")
def round_save(
    rid: int,
    request: Request,
    at_time: str = Form(""),
    note: str = Form(""),
    db: Session = Depends(get_db),
):
    """시각은 매월·매 학기 바뀌므로 여기서 고친다."""
    _, redirect = _guard(request, db)
    if redirect:
        return redirect
    r = db.get(Round, rid)
    if r:
        r.at_time = at_time.strip() or r.at_time
        r.note = note.strip()
        db.commit()
    return _back("차수 시각 변경")


@router.post("/settings/round/{rid}/sign")
def round_sign(rid: int, request: Request, db: Session = Depends(get_db)):
    _, redirect = _guard(request, db)
    if redirect:
        return redirect
    r = db.get(Round, rid)
    if r:
        r.needs_sign = not r.needs_sign
        db.commit()
        return _back(f"{r.name} — {'서명을 받습니다' if r.needs_sign else '체크만 합니다'}")
    return _back()


# ── 학원 ────────────────────────────────────────────────

@router.post("/settings/academy/add")
def academy_add(request: Request, name: str = Form(""), db: Session = Depends(get_db)):
    me, redirect = _guard(request, db)
    if redirect:
        return redirect
    name = name.strip()
    if not name:
        return _back("학원 이름을 입력해 주세요")
    if db.scalar(select(Academy).where(Academy.kinder_id == me.kinder_id, Academy.name == name)):
        return _back("이미 있는 학원입니다")
    db.add(Academy(kinder_id=me.kinder_id, name=name))
    db.commit()
    return _back(f"{name} 추가")


@router.post("/settings/academy/{aid}/delete")
def academy_delete(aid: int, request: Request, db: Session = Depends(get_db)):
    _, redirect = _guard(request, db)
    if redirect:
        return redirect
    if db.scalar(select(func.count(PlanEntry.id)).where(PlanEntry.academy_id == aid)):
        return _back("이 학원으로 가는 아이가 있어 삭제할 수 없습니다")
    a = db.get(Academy, aid)
    if a:
        db.delete(a)
        db.commit()
    return _back("학원 삭제")


# ── 유치원 정보 ─────────────────────────────────────────

@router.post("/settings/kinder")
def kinder_save(
    request: Request,
    kinder_name: str = Form(""),
    route_note: str = Form(""),
    db: Session = Depends(get_db),
):
    me, redirect = _guard(request, db)
    if redirect:
        return redirect
    k = db.get(Kindergarten, me.kinder_id)
    k.name = kinder_name.strip() or k.name
    k.route_note = route_note.strip()
    db.commit()
    return _back("유치원 정보 저장")
