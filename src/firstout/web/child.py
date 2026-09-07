"""원아 한 명 — 주간 계획·인계자·귀가 기록.

명부는 엑셀로 한 번에 올리지만, 실제로 바뀌는 건 늘 한 명씩이다.
「수요일부터 태권도 차 타요」, 「이모가 인계자로 추가돼요」, 「전학 왔어요」.
그때마다 150명을 다시 올릴 수는 없으므로 이 화면이 필요하다.

받아둔 서명도 여기서 본다. 인계 증빙으로 받아놓고 되짚어 볼 수 없으면
받는 의미가 절반이다. (서명 그림은 한 달 뒤 지워진다 — retention 참고)

누가 무엇을 하는가
    선생님    주간 계획 · 인계자 · 특이사항 — 매일 생기는 일이다
    총괄 관리자  원아 추가 · 퇴원 — 정원이 바뀌는 일이다
"""

from __future__ import annotations

from fastapi import APIRouter, Depends, Form, Request
from fastapi.responses import RedirectResponse
from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload

from .. import flash, service
from ..config import WEEKDAYS
from ..db import get_db
from ..models import DEP_DONE, Academy, Child, Departure, Guardian, PlanEntry

router = APIRouter()

RECENT = 20        # 최근 귀가 기록을 이만큼 보여준다


def _me(request: Request, db: Session):
    from ..main import current_user

    me = current_user(request, db)
    if me is None:
        return None, RedirectResponse("/signin", status_code=303)
    if me.kinder_id is None:
        return None, RedirectResponse("/", status_code=303)
    return me, None


def _child(db: Session, cid: int, me) -> Child | None:
    """남의 유치원 아이는 번호를 알아도 열 수 없다."""
    c = db.get(Child, cid)
    return c if c and c.kinder_id == me.kinder_id else None


def _back(cid: int, msg: str = "") -> RedirectResponse:
    return flash.put(RedirectResponse(f"/child/{cid}", status_code=303), msg)


def _academies(db: Session, kinder_id: int) -> list[Academy]:
    return list(
        db.scalars(
            select(Academy).where(Academy.kinder_id == kinder_id).order_by(Academy.name)
        )
    )


def _entry(db: Session, child: Child, weekday: int) -> PlanEntry:
    p = next((x for x in child.plan if x.weekday == weekday), None)
    if p is None:
        p = PlanEntry(child_id=child.id, weekday=weekday)
        db.add(p)
        db.flush()
    return p


# ── 보기 ────────────────────────────────────────────────

@router.get("/child/{cid}")
def show(cid: int, request: Request, db: Session = Depends(get_db)):
    from ..main import page

    me, redirect = _me(request, db)
    if redirect:
        return redirect
    child = _child(db, cid, me)
    if child is None:
        return RedirectResponse("/roster", status_code=303)

    plans = {p.weekday: p for p in child.plan}
    history = list(
        db.scalars(
            select(Departure)
            .where(Departure.child_id == child.id, Departure.status == DEP_DONE)
            .options(selectinload(Departure.round), selectinload(Departure.teacher))
            .order_by(Departure.on_date.desc())
            .limit(RECENT)
        )
    )
    return page(
        request, "child.html", db, me,
        child=child,
        academies=_academies(db, me.kinder_id),
        plans=plans,
        history=history,
    )


# ── 기본 정보 ───────────────────────────────────────────

@router.post("/child/{cid}/save")
def save(
    cid: int,
    request: Request,
    name: str = Form(""),
    class_id: str = Form(""),
    note: str = Form(""),
    db: Session = Depends(get_db),
):
    me, redirect = _me(request, db)
    if redirect:
        return redirect
    child = _child(db, cid, me)
    if child is None:
        return RedirectResponse("/roster", status_code=303)

    if name.strip():
        child.name = name.strip()[:40]
    if class_id.isdigit():
        room = next((r for r in service.classes(db, me.kinder_id) if r.id == int(class_id)), None)
        if room:
            child.class_id = room.id
    child.note = note.strip()[:200]
    db.commit()
    return _back(cid, f"{child.name} 정보를 저장했습니다")


@router.post("/child/{cid}/leave")
def leave(cid: int, request: Request, db: Session = Depends(get_db)):
    """퇴원 처리 — 지우지 않고 멈춘다.

    지난 귀가 기록의 주인이 사라지면 「그때 누가 데려갔나」를 되짚을 수 없다.
    다시 오는 아이도 있으므로 되돌릴 수 있게 둔다.
    """
    me, redirect = _me(request, db)
    if redirect:
        return redirect
    if not me.is_admin:
        return _back(cid, "정원을 바꾸는 일은 총괄 관리자만 하실 수 있습니다")
    child = _child(db, cid, me)
    if child is None:
        return RedirectResponse("/roster", status_code=303)

    child.active = not child.active
    word = "다시 등원" if child.active else "퇴원"
    room = child.classroom.name if child.classroom else ""
    request.state.audit_note = f"{child.name}{' · ' + room if room else ''} {word}"
    db.commit()
    return _back(cid, f"{child.name} — {word} 처리했습니다")


# ── 주간 계획 ───────────────────────────────────────────

@router.post("/child/{cid}/plan")
def plan(
    cid: int,
    request: Request,
    weekday: int = Form(-1),
    how: str = Form(""),
    at_time: str = Form(""),
    db: Session = Depends(get_db),
):
    """요일 한 칸을 고친다.

    how 는 「」(정규 후 귀가) · 「r:3」(차수) · 「a:2」(학원차) 중 하나다.
    학원차는 개별 차수에 함께 나가되 서명 없이 태우기만 한다.
    """
    me, redirect = _me(request, db)
    if redirect:
        return redirect
    child = _child(db, cid, me)
    if child is None or not (0 <= weekday < len(WEEKDAYS)):
        return RedirectResponse("/roster", status_code=303)

    entry = _entry(db, child, weekday)
    entry.round_id = None
    entry.academy_id = None
    entry.time_override = ""

    kind, _, num = how.partition(":")
    if kind == "r" and num.isdigit():
        rnd = next((r for r in service.rounds(db, me.kinder_id) if r.id == int(num)), None)
        if rnd:
            entry.round_id = rnd.id
            entry.time_override = at_time.strip()[:10]
    elif kind == "a" and num.isdigit():
        aca = next((a for a in _academies(db, me.kinder_id) if a.id == int(num)), None)
        if aca:
            entry.academy_id = aca.id
            # 학원차는 개별 차수 시간에 맞춰 나간다
            first = next((r for r in service.rounds(db, me.kinder_id) if r.kind == "개별"), None)
            entry.round_id = first.id if first else None

    db.commit()
    return _back(cid, f"{child.name} · {WEEKDAYS[weekday]}요일 계획을 바꿨습니다")


# ── 인계자 ──────────────────────────────────────────────

@router.post("/child/{cid}/guardian/add")
def guardian_add(
    cid: int,
    request: Request,
    name: str = Form(""),
    relation: str = Form(""),
    phone: str = Form(""),
    db: Session = Depends(get_db),
):
    me, redirect = _me(request, db)
    if redirect:
        return redirect
    child = _child(db, cid, me)
    if child is None:
        return RedirectResponse("/roster", status_code=303)
    if not name.strip():
        return _back(cid, "인계자 성함을 적어주세요")

    db.add(
        Guardian(
            child_id=child.id,
            name=name.strip()[:40],
            relation=relation.strip()[:20] or "보호자",
            phone=phone.strip()[:30],
            is_default=not child.guardians,     # 처음 등록되는 분이 기본이 된다
            seq=len(child.guardians),
        )
    )
    db.commit()
    return _back(cid, f"{name.strip()} 님을 인계자로 추가했습니다")


def _guardian(db: Session, child: Child, gid: int) -> Guardian | None:
    return next((g for g in child.guardians if g.id == gid), None)


@router.post("/child/{cid}/guardian/{gid}/save")
def guardian_save(
    cid: int,
    gid: int,
    request: Request,
    name: str = Form(""),
    relation: str = Form(""),
    phone: str = Form(""),
    db: Session = Depends(get_db),
):
    """연락처는 비워두면 그대로 둔다 — 화면에 가려서 보여주기 때문이다.

    가린 값을 그대로 되돌려 받아 저장하면 「010-****-5678」 이 진짜 번호가 되어
    결석 확인 전화를 걸 수 없게 된다.
    """
    me, redirect = _me(request, db)
    if redirect:
        return redirect
    child = _child(db, cid, me)
    if child is None:
        return RedirectResponse("/roster", status_code=303)
    g = _guardian(db, child, gid)
    if g is None:
        return _back(cid)

    if name.strip():
        g.name = name.strip()[:40]
    g.relation = relation.strip()[:20] or g.relation
    if phone.strip():
        g.phone = phone.strip()[:30]
    db.commit()
    return _back(cid, f"{g.name} 님 정보를 저장했습니다")


@router.post("/child/{cid}/guardian/{gid}/default")
def guardian_default(cid: int, gid: int, request: Request, db: Session = Depends(get_db)):
    """기본 인계자 — 서명 창에 처음 뜨는 분이다."""
    me, redirect = _me(request, db)
    if redirect:
        return redirect
    child = _child(db, cid, me)
    if child is None:
        return RedirectResponse("/roster", status_code=303)
    g = _guardian(db, child, gid)
    if g is None:
        return _back(cid)

    for other in child.guardians:
        other.is_default = other.id == g.id
    db.commit()
    return _back(cid, f"{g.name} 님을 기본 인계자로 두었습니다")


@router.post("/child/{cid}/guardian/{gid}/delete")
def guardian_delete(cid: int, gid: int, request: Request, db: Session = Depends(get_db)):
    me, redirect = _me(request, db)
    if redirect:
        return redirect
    child = _child(db, cid, me)
    if child is None:
        return RedirectResponse("/roster", status_code=303)
    g = _guardian(db, child, gid)
    if g is None:
        return _back(cid)
    if len(child.guardians) < 2:
        return _back(cid, "인계자가 한 분뿐이라 지울 수 없습니다")

    name, was_default = g.name, g.is_default

    # 관계에서 빼야 목록이 바로 갱신된다. db.delete() 만 하면 지운 사람이 목록에
    # 그대로 남아 있어, 그 사람에게 기본을 넘기고 함께 사라진다 —
    # 그러면 기본 인계자가 아무도 없어져 서명 창이 매번 비어 나온다.
    child.guardians.remove(g)
    db.flush()
    if was_default:
        left = sorted(child.guardians, key=lambda x: x.seq)
        if left:
            left[0].is_default = True
    db.commit()
    return _back(cid, f"{name} 님을 인계자에서 뺐습니다")


# ── 원아 추가 ───────────────────────────────────────────

@router.post("/roster/add")
def add(
    request: Request,
    name: str = Form(""),
    class_id: str = Form(""),
    g_name: str = Form(""),
    g_relation: str = Form(""),
    g_phone: str = Form(""),
    db: Session = Depends(get_db),
):
    """전학 온 아이 한 명. 주간 계획은 만든 뒤 그 아이 화면에서 정한다."""
    me, redirect = _me(request, db)
    if redirect:
        return redirect
    if not me.is_admin:
        return flash.put(RedirectResponse("/roster", status_code=303),
                         "원아 등록은 총괄 관리자만 하실 수 있습니다")

    name = name.strip()
    room = next(
        (r for r in service.classes(db, me.kinder_id) if str(r.id) == class_id), None
    )
    if not name or room is None:
        return flash.put(RedirectResponse("/roster", status_code=303),
                         "이름과 반을 정해주세요")

    child = Child(kinder_id=me.kinder_id, name=name[:40], class_id=room.id)
    db.add(child)
    db.flush()
    if g_name.strip():
        db.add(
            Guardian(
                child_id=child.id,
                name=g_name.strip()[:40],
                relation=g_relation.strip()[:20] or "보호자",
                phone=g_phone.strip()[:30],
                is_default=True,
                seq=0,
            )
        )
    db.commit()
    return _back(child.id, f"{child.name} 등록 — 이제 주간 계획을 정해주세요")
