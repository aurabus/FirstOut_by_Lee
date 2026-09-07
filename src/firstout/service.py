"""업무 규칙.

여기 있는 함수들이 이 프로그램의 핵심이다.
"주간 계획 + 오늘 출결" 에서 "오늘 차수별 명단" 을 만들어낸다.
선생님이 매주 같은 이름을 다시 적지 않아도 되는 이유가 이것이다.
"""

from __future__ import annotations

import datetime as dt
from dataclasses import dataclass

from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload

from .models import (
    ATT_ABSENT,
    ATT_EARLY,
    DEP_CALLED,
    DEP_DONE,
    KG_ACTIVE,
    Attendance,
    Child,
    ClassRoom,
    Departure,
    Kindergarten,
    PlanEntry,
    Round,
)

LATE_MINUTES = 5  # 호출 후 이만큼 지나면 붉게 표시
NO_CONTACT = "연락없음"  # 결석 사유 — 보호자에게 확인 전화가 필요하다


# ── 조회 도우미 ─────────────────────────────────────────

def kindergartens(db: Session) -> list[Kindergarten]:
    """실제로 쓸 수 있는 유치원 목록. 승인대기·정지는 빼고 보여준다."""
    return list(
        db.scalars(
            select(Kindergarten)
            .where(Kindergarten.status == KG_ACTIVE)
            .order_by(Kindergarten.seq, Kindergarten.id)
        )
    )


def classes(db: Session, kinder_id: int) -> list[ClassRoom]:
    return list(
        db.scalars(
            select(ClassRoom)
            .where(ClassRoom.kinder_id == kinder_id)
            .order_by(ClassRoom.seq, ClassRoom.id)
        )
    )


def rounds(db: Session, kinder_id: int) -> list[Round]:
    return list(
        db.scalars(
            select(Round).where(Round.kinder_id == kinder_id).order_by(Round.seq, Round.id)
        )
    )


def round_by_key(db: Session, kinder_id: int, key: str) -> Round | None:
    return db.scalar(select(Round).where(Round.kinder_id == kinder_id, Round.key == key))


def weekday_index(day: dt.date) -> int | None:
    """월~금이면 0~4, 주말이면 None."""
    wd = day.weekday()
    return wd if wd <= 4 else None


# ── 오늘 한 아이의 상태 ─────────────────────────────────

@dataclass
class Row:
    """명단 한 줄. 화면과 인쇄가 공통으로 쓴다."""

    child: Child
    plan: PlanEntry | None
    att: Attendance | None
    dep: Departure | None

    @property
    def academy(self) -> str:
        return self.plan.academy.name if self.plan and self.plan.academy else ""

    @property
    def is_academy(self) -> bool:
        return bool(self.plan and self.plan.academy_id)

    @property
    def excluded(self) -> bool:
        """결석·조퇴한 아이는 오늘 명단에서 빠진다."""
        return bool(self.att and self.att.status in (ATT_ABSENT, ATT_EARLY))

    @property
    def done(self) -> bool:
        return bool(self.dep and self.dep.status == DEP_DONE)

    @property
    def called(self) -> bool:
        return bool(self.dep and self.dep.status == DEP_CALLED)

    @property
    def needs_sign(self) -> bool:
        """사람에게 건네면 서명, 차에 태우면 체크만.

        학원차는 개별 차수에 함께 나가지만 매일 정해진 기사라 체크만 한다.
        """
        if not self.plan or not self.plan.round:
            return False
        if self.is_academy:
            return False
        return self.plan.round.needs_sign

    @property
    def at_time(self) -> str:
        if self.plan and self.plan.time_override:
            return self.plan.time_override
        if self.plan and self.plan.round:
            return self.plan.round.at_time
        return ""

    @property
    def label(self) -> str:
        if not self.plan or not self.plan.round:
            return "정규"
        if self.is_academy:
            return f"학원차 {self.academy}"
        return self.plan.round.name

    @property
    def added_today(self) -> bool:
        """주간 계획과 다르게 오늘만 이 차수에 들어온 아이."""
        if not self.dep or not self.dep.round_id:
            return False
        planned = self.plan.round_id if self.plan else None
        return planned != self.dep.round_id

    def waited_seconds(self, now: dt.datetime) -> int:
        if not self.dep or not self.dep.called_at:
            return 0
        return max(0, int((now - self.dep.called_at).total_seconds()))

    def is_late(self, now: dt.datetime) -> bool:
        return self.called and self.waited_seconds(now) >= LATE_MINUTES * 60


def day_rows(
    db: Session, kinder_id: int, day: dt.date, class_id: int | None = None
) -> list[Row]:
    """그날 그 유치원에 재원 중인 아이 전원의 상태를 한 번에 읽는다."""
    wd = weekday_index(day)

    q = (
        select(Child)
        .where(Child.active.is_(True), Child.kinder_id == kinder_id)
        .options(
            selectinload(Child.classroom),
            selectinload(Child.guardians),
            selectinload(Child.plan).selectinload(PlanEntry.round),
            selectinload(Child.plan).selectinload(PlanEntry.academy),
        )
    )
    if class_id:
        q = q.where(Child.class_id == class_id)
    kids = list(db.scalars(q))
    if not kids:
        return []

    ids = [k.id for k in kids]
    atts = {
        a.child_id: a
        for a in db.scalars(
            select(Attendance).where(Attendance.on_date == day, Attendance.child_id.in_(ids))
        )
    }
    deps = {
        d.child_id: d
        for d in db.scalars(
            select(Departure)
            .where(Departure.on_date == day, Departure.child_id.in_(ids))
            .options(selectinload(Departure.round))
        )
    }

    order = {c.id: (c.seq, c.id) for c in classes(db, kinder_id)}
    rows = [
        Row(
            child=k,
            plan=next((p for p in k.plan if p.weekday == wd), None) if wd is not None else None,
            att=atts.get(k.id),
            dep=deps.get(k.id),
        )
        for k in kids
    ]
    rows.sort(key=lambda r: (order.get(r.child.class_id, (99, 99)), r.child.name))
    return rows


# ── 차수별 명단 ─────────────────────────────────────────

def rows_for_round(rows: list[Row], rnd: Round) -> list[Row]:
    """오늘 이 차수로 나가는 아이들. 결석·조퇴는 제외한다.

    그날의 배정(Departure.round_id)이 있으면 주간 계획보다 우선한다.
    "오늘만 할머니가 데리러 오신대요" 같은 일이 매일 생기는데,
    그때마다 주간 계획을 고치면 다음 주까지 바뀌어 버리기 때문이다.
    """
    out = []
    for r in rows:
        if r.excluded:
            continue
        if r.dep and r.dep.round_id:
            if r.dep.round_id == rnd.id:
                out.append(r)
            continue                      # 오늘은 다른 차수로 옮겨졌다
        if r.plan and r.plan.round_id == rnd.id:
            out.append(r)
    return out


def excluded_for_round(rows: list[Row], rnd: Round) -> list[Row]:
    """이 차수 대상이었지만 결석·조퇴로 빠진 아이 — 명단 아래에 표시한다."""
    out = []
    for r in rows:
        if not r.excluded:
            continue
        here = (r.dep.round_id == rnd.id) if (r.dep and r.dep.round_id) else (
            bool(r.plan) and r.plan.round_id == rnd.id
        )
        if here:
            out.append(r)
    return out


def group_by_class(rows: list[Row]) -> list[tuple[ClassRoom, list[Row]]]:
    """반 순서(= 데려오는 동선)대로 묶는다."""
    out: list[tuple[ClassRoom, list[Row]]] = []
    for r in rows:
        if out and out[-1][0].id == r.child.class_id:
            out[-1][1].append(r)
        else:
            out.append((r.child.classroom, [r]))
    return out


# ── 집계 ────────────────────────────────────────────────

@dataclass
class ClassStat:
    room: ClassRoom
    total: int = 0
    absent: int = 0
    early: int = 0
    home: int = 0
    staying: int = 0
    waiting: int = 0
    late: bool = False


def class_stats(
    db: Session, kinder_id: int, rows: list[Row], now: dt.datetime
) -> list[ClassStat]:
    stats = {c.id: ClassStat(room=c) for c in classes(db, kinder_id)}
    for r in rows:
        s = stats.get(r.child.class_id)
        if s is None:
            continue
        s.total += 1
        if r.att and r.att.status == ATT_ABSENT:
            s.absent += 1
        elif r.att and r.att.status == ATT_EARLY:
            s.early += 1
        elif r.done:
            s.home += 1
        else:
            s.staying += 1
            if r.called:
                s.waiting += 1
                if r.is_late(now):
                    s.late = True
    return [stats[c.id] for c in classes(db, kinder_id)]


# ── 오늘 챙겨야 할 것 ───────────────────────────────────

OVERDUE_GRACE = 10   # 차수 시각이 지나고 이만큼은 기다려 준다 (분)


def no_contact(rows: list[Row]) -> list[Row]:
    """결석인데 사유가 「연락없음」인 아이.

    담임 화면에만 뜨고 있었다. 아이가 오지 않았는데 연락도 닿지 않는 것은
    원장이 가장 먼저 알아야 하는 일이다.
    """
    return [
        r for r in rows
        if r.att and r.att.status == ATT_ABSENT and r.att.reason == NO_CONTACT
    ]


def _minutes(at_time: str) -> int | None:
    """「15:40」 을 분으로. 이상한 값이면 None."""
    try:
        h, _, m = at_time.partition(":")
        h, m = int(h), int(m)
    except (ValueError, TypeError):
        return None
    return h * 60 + m if 0 <= h < 24 and 0 <= m < 60 else None


def overdue(rows: list[Row], rnd: Round, now: dt.datetime, day: dt.date) -> list[Row]:
    """그 차수의 시각이 지났는데 아직 안 나간 아이.

    「호출하고 5분」과는 다른 신호다. 그쪽은 부르고 안 오는 것이고,
    이쪽은 **아무도 아직 손대지 않은** 것이다. 4시 20분이 지났는데 2차 차량에
    셋이 남아 있으면 그게 사고 신호다.

    지난 날짜를 들춰볼 때는 세지 않는다 — 그때는 이미 다 끝난 일이다.
    """
    if day != now.date():
        return []
    at = _minutes(rnd.at_time)
    if at is None or (now.hour * 60 + now.minute) < at + OVERDUE_GRACE:
        return []
    return [r for r in rows_for_round(rows, rnd) if not r.done]
