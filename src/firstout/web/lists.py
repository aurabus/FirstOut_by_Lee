"""귀가 명단 — 이 프로그램에서 선생님이 가장 오래 보는 화면.

지금 쓰시는 구글시트의 「개별 · 차량 · 돌봄」 세 탭을 대신한다.
차이는 이름을 다시 적지 않는다는 것 하나뿐이다. 주간 계획에서 매일 자동으로 만들어진다.

처리 방식이 둘로 갈린다.
  차에 태울 때  → 이름을 누르면 바로 체크 (확인 창 없음)
  사람에게 건넬 때 → 인계자 확인 + 서명
"""

from __future__ import annotations

import datetime as dt

from fastapi import APIRouter, Depends, Form, Request
from fastapi.responses import RedirectResponse
from sqlalchemy import select
from sqlalchemy.orm import Session

from .. import service
from ..db import get_db
from ..models import DEP_CALLED, DEP_DONE, DEP_WAITING, Child, Departure

router = APIRouter()


def _dep(db: Session, child_id: int, day: dt.date, round_id: int | None) -> Departure:
    """그날의 귀가 기록을 가져오거나 만든다."""
    dep = db.scalar(
        select(Departure).where(Departure.child_id == child_id, Departure.on_date == day)
    )
    if dep is None:
        dep = Departure(child_id=child_id, on_date=day, round_id=round_id, status=DEP_WAITING)
        db.add(dep)
        db.flush()
    return dep


def _back(key: str, msg: str = "", day: str = "") -> RedirectResponse:
    """처리 후 보던 명단으로 돌아간다. 조회 중이던 날짜를 잃지 않는다."""
    q = f"?msg={msg}" + (f"&d={day}" if day else "")
    return RedirectResponse(f"/list/{key}{q}", status_code=303)


@router.get("/list/{key}")
def show(request: Request, key: str, db: Session = Depends(get_db), msg: str = "", d: str = ""):
    from ..main import current_teacher, page, pick_date

    me = current_teacher(request, db)
    if me is None:
        return RedirectResponse("/login", status_code=303)

    rnd = service.round_by_key(db, key)
    if rnd is None:
        return RedirectResponse("/board", status_code=303)

    day = pick_date(d)
    rows = service.day_rows(db, day)
    target = service.rows_for_round(rows, rnd)

    return page(
        request, "list.html", db, me,
        day=day, d=d,
        rnd=rnd,
        groups=service.group_by_class(target),
        target=target,
        done=sum(1 for r in target if r.done),
        sign_any=any(r.needs_sign for r in target),
        sign_all=bool(target) and all(r.needs_sign for r in target),
        skipped=service.excluded_for_round(rows, rnd),
        weekend=service.weekday_index(day) is None,
        msg=msg,
    )


@router.post("/list/{key}/{cid}/check")
def check(
    key: str,
    cid: int,
    request: Request,
    how: str = Form(""),
    d: str = Form(""),
    db: Session = Depends(get_db),
):
    """차에 태우는 경우 — 확인 창 없이 바로 체크한다.

    12명을 태우면서 매번 확인을 누르면 현장에서 못 쓴다는 의견을 반영했다.
    """
    from ..main import current_teacher, now, pick_date

    me = current_teacher(request, db)
    if me is None:
        return RedirectResponse("/login", status_code=303)

    rnd = service.round_by_key(db, key)
    child = db.get(Child, cid)
    if rnd is None or child is None:
        return _back(key, "", d)

    dep = _dep(db, cid, pick_date(d), rnd.id)
    dep.status = DEP_DONE
    dep.done_at = now()
    dep.handled_by = me.id
    dep.how = how or rnd.name
    dep.round_id = rnd.id
    db.commit()
    return _back(key, f"{child.name} 귀가 처리", d)


@router.post("/list/{key}/{cid}/sign")
def sign(
    key: str,
    cid: int,
    request: Request,
    receiver: str = Form(""),
    signature: str = Form(""),
    memo: str = Form(""),
    d: str = Form(""),
    db: Session = Depends(get_db),
):
    """사람에게 건네는 경우 — 인계자와 서명을 남긴다.

    서명이 없으면 처리하지 않는다. 나중에 "누가 데려갔나"를 확인할 근거이기 때문이다.
    """
    from ..main import current_teacher, now, pick_date

    me = current_teacher(request, db)
    if me is None:
        return RedirectResponse("/login", status_code=303)

    rnd = service.round_by_key(db, key)
    child = db.get(Child, cid)
    if rnd is None or child is None:
        return _back(key, "", d)
    if not signature.startswith("data:image/"):
        return _back(key, "서명을 받아주세요", d)

    dep = _dep(db, cid, pick_date(d), rnd.id)
    dep.status = DEP_DONE
    dep.done_at = now()
    dep.handled_by = me.id
    dep.receiver = receiver
    dep.how = receiver or "보호자 인계"
    dep.signature = signature
    dep.memo = memo.strip()
    dep.round_id = rnd.id
    db.commit()
    return _back(key, f"{child.name} 인계 완료 · 서명 받음", d)


@router.post("/list/{key}/{cid}/call")
def call(
    key: str, cid: int, request: Request, d: str = Form(""), db: Session = Depends(get_db)
):
    """전화만 받은 상태 — 여기서부터 대기 시간이 흐른다."""
    from ..main import current_teacher, now, pick_date

    me = current_teacher(request, db)
    if me is None:
        return RedirectResponse("/login", status_code=303)

    rnd = service.round_by_key(db, key)
    child = db.get(Child, cid)
    if rnd is None or child is None:
        return _back(key, "", d)

    dep = _dep(db, cid, pick_date(d), rnd.id)
    dep.status = DEP_CALLED
    dep.called_at = now()
    db.commit()
    return _back(key, f"{child.name} 인계대기 등록", d)


@router.post("/list/{key}/{cid}/undo")
def undo(
    key: str, cid: int, request: Request, d: str = Form(""), db: Session = Depends(get_db)
):
    """잘못 누른 것을 되돌린다. 특이사항은 지우지 않는다."""
    from ..main import current_teacher, pick_date

    me = current_teacher(request, db)
    if me is None:
        return RedirectResponse("/login", status_code=303)

    dep = db.scalar(
        select(Departure).where(Departure.child_id == cid, Departure.on_date == pick_date(d))
    )
    if dep:
        dep.status = DEP_WAITING
        dep.done_at = None
        dep.called_at = None
        dep.signature = ""
        dep.receiver = ""
        dep.how = ""
        db.commit()
    return _back(key, "처리 취소", d)


@router.post("/list/{key}/{cid}/memo")
def memo(
    key: str,
    cid: int,
    request: Request,
    memo: str = Form(""),
    d: str = Form(""),
    db: Session = Depends(get_db),
):
    """특이사항 — 차에 태우는 아이도 적을 수 있다."""
    from ..main import current_teacher, pick_date

    me = current_teacher(request, db)
    if me is None:
        return RedirectResponse("/login", status_code=303)

    rnd = service.round_by_key(db, key)
    dep = _dep(db, cid, pick_date(d), rnd.id if rnd else None)
    dep.memo = memo.strip()
    db.commit()
    return _back(key, "특이사항 저장", d)
