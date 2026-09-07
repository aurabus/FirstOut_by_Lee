"""출결 등록 — 담임이 아침에 쓰는 화면.

여기서 결석·조퇴로 바꾸면 그날 귀가 명단에서 자동으로 빠진다.
이 화면이 없으면 안 온 아이를 명단에서 계속 찾게 되므로, 하루의 시작점이다.

기록이 없으면 「출석」으로 본다. 대신 확인을 눌렀는지는 따로 세어,
담임이 오늘 출결을 봤는지 알 수 있게 한다.
"""

from __future__ import annotations

from fastapi import APIRouter, Depends, Form, Request
from fastapi.responses import RedirectResponse
from sqlalchemy import select
from sqlalchemy.orm import Session

from .. import flash, service
from ..db import get_db
from ..models import ATT_ABSENT, ATT_EARLY, ATT_PRESENT, Attendance, Child

router = APIRouter()

REASONS = ["질병", "가정", "기타", "연락없음"]
NO_CONTACT = "연락없음"


def _guard(request: Request, db: Session):
    from ..main import current_user

    me = current_user(request, db)
    if me is None:
        return None, RedirectResponse("/signin", status_code=303)
    if me.kinder_id is None:
        return None, RedirectResponse("/", status_code=303)
    return me, None


def _back(cls: int | None, day: str = "", msg: str = "") -> RedirectResponse:
    q = []
    if cls:
        q.append(f"cls={cls}")
    if day:
        q.append(f"d={day}")
    url = "/attend" + ("?" + "&".join(q) if q else "")
    return flash.put(RedirectResponse(url, status_code=303), msg)


def _row(db: Session, child: Child, day) -> Attendance:
    a = db.scalar(
        select(Attendance).where(Attendance.child_id == child.id, Attendance.on_date == day)
    )
    if a is None:
        a = Attendance(child_id=child.id, on_date=day, status=ATT_PRESENT)
        db.add(a)
        db.flush()
    return a


def _child_of(db: Session, cid: int, me) -> Child | None:
    c = db.get(Child, cid)
    return c if c and c.kinder_id == me.kinder_id else None


@router.get("/attend")
def attend_view(
    request: Request, db: Session = Depends(get_db), cls: int | None = None, d: str = ""
):
    from ..main import page, pick_date

    me, redirect = _guard(request, db)
    if redirect:
        return redirect

    rooms = service.classes(db, me.kinder_id)
    if not rooms:
        return page(request, "attend.html", db, me, room=None, rows=[], rooms=[])

    # 담임은 자기 반이 먼저 열린다
    room = next((r for r in rooms if r.id == cls), None)
    if room is None:
        room = next((r for r in rooms if r.id == me.class_id), rooms[0])

    day = pick_date(d)
    rows = service.day_rows(db, me.kinder_id, day, class_id=room.id)
    rows.sort(key=lambda r: r.child.name)

    counted = {"출석": 0, "결석": 0, "조퇴": 0}
    for r in rows:
        counted[r.att.status if r.att else ATT_PRESENT] += 1

    return page(
        request, "attend.html", db, me,
        day=day, d=d,
        room=room, rooms=rooms, rows=rows,
        counted=counted,
        checked=sum(1 for r in rows if r.att is not None),
        reasons=REASONS,
        weekend=service.weekday_index(day) is None,
    )


@router.post("/attend/{cid}")
def attend_set(
    cid: int,
    request: Request,
    status: str = Form(""),
    reason: str = Form(""),
    cls: int | None = Form(None),
    d: str = Form(""),
    db: Session = Depends(get_db),
):
    """출결을 바꾸거나 결석 사유만 고른다."""
    from ..main import now, pick_date

    me, redirect = _guard(request, db)
    if redirect:
        return redirect

    child = _child_of(db, cid, me)
    if child is None:
        return _back(cls, d)

    day = pick_date(d)
    a = _row(db, child, day)
    a.teacher_id = me.id

    if reason:
        # 사유만 고른 경우 — 결석 상태는 그대로 둔다
        a.status = ATT_ABSENT
        a.reason = reason if reason in REASONS else ""
        db.commit()
        note = " — 보호자 확인이 필요합니다" if reason == NO_CONTACT else ""
        return _back(cls, d, f"{child.name} 결석 사유 · {reason}{note}")

    if status == ATT_ABSENT:
        a.status = ATT_ABSENT
        a.reason = a.reason or "질병"
        a.left_at = ""
    elif status == ATT_EARLY:
        a.status = ATT_EARLY
        a.reason = ""
        a.left_at = now().strftime("%H:%M")
    else:
        a.status = ATT_PRESENT
        a.reason = ""
        a.left_at = ""

    db.commit()
    tail = f" {a.left_at}" if a.status == ATT_EARLY else ""
    return _back(cls, d, f"{child.name} · {a.status}{tail}")


@router.post("/attend/all/{room_id}")
def attend_all(
    room_id: int,
    request: Request,
    d: str = Form(""),
    db: Session = Depends(get_db),
):
    """전체 출석 처리 — 결석·조퇴로 이미 바꾼 아이는 건드리지 않는다.

    보통 결석이 소수라, 전체를 찍고 몇 명만 고치는 편이 훨씬 빠르다.
    """
    from ..main import pick_date

    me, redirect = _guard(request, db)
    if redirect:
        return redirect

    room = next((r for r in service.classes(db, me.kinder_id) if r.id == room_id), None)
    if room is None:
        return _back(None, d)

    day = pick_date(d)
    kids = list(
        db.scalars(
            select(Child).where(
                Child.kinder_id == me.kinder_id,
                Child.class_id == room.id,
                Child.active.is_(True),
            )
        )
    )
    made = 0
    for c in kids:
        a = db.scalar(
            select(Attendance).where(Attendance.child_id == c.id, Attendance.on_date == day)
        )
        if a is None:
            db.add(Attendance(child_id=c.id, on_date=day, status=ATT_PRESENT, teacher_id=me.id))
            made += 1
    db.commit()
    note = f"{room.name} — {made}명 출석 확인" if made else "이미 모두 확인되었습니다"
    return _back(room.id, d, note)
