"""데이터 구조.

핵심 설계
- 반·차량·차수·학원은 모두 **설정 자료**다. 유치원마다 다르므로 코드에 박지 않는다.
- 아이의 귀가 방법은 "아이 × 요일" 단위(PlanEntry)로 저장한다. 요일마다 다르기 때문.
- 하루치 기록(Attendance·Departure)은 날짜별로 따로 쌓아 과거를 그대로 보존한다.
"""

from __future__ import annotations

import datetime as dt

from sqlalchemy import (
    Boolean,
    Date,
    DateTime,
    ForeignKey,
    Integer,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship


class Base(DeclarativeBase):
    pass


# ── 설정 ────────────────────────────────────────────────

class Setting(Base):
    """유치원 단위 설정 — 한 행만 쓴다."""

    __tablename__ = "setting"
    id: Mapped[int] = mapped_column(primary_key=True)
    kinder_name: Mapped[str] = mapped_column(String(60), default="우리유치원")
    route_note: Mapped[str] = mapped_column(String(120), default="")
    care_close: Mapped[str] = mapped_column(String(10), default="19:00")


class ClassRoom(Base):
    """반. seq 순서가 곧 아이를 데려오는 동선 순서다."""

    __tablename__ = "classroom"
    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(40), unique=True)
    seq: Mapped[int] = mapped_column(Integer, default=0)

    children: Mapped[list[Child]] = relationship(back_populates="classroom")


class Bus(Base):
    __tablename__ = "bus"
    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(40), unique=True)
    seq: Mapped[int] = mapped_column(Integer, default=0)


class Academy(Base):
    __tablename__ = "academy"
    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(40), unique=True)


class Round(Base):
    """귀가 차수.

    kind 는 처리 방식을 가른다.
      개별 = 사람에게 건넴 → 서명
      차량 = 차에 태움     → 체크만
      돌봄 = 사람에게 건넴 → 서명
    학원차로 가는 아이는 개별 차수에 함께 나가지만 서명은 받지 않는다.
    """

    __tablename__ = "round"
    id: Mapped[int] = mapped_column(primary_key=True)
    key: Mapped[str] = mapped_column(String(20), unique=True)
    name: Mapped[str] = mapped_column(String(40))
    kind: Mapped[str] = mapped_column(String(10))  # 개별 · 차량 · 돌봄
    seq: Mapped[int] = mapped_column(Integer, default=0)
    at_time: Mapped[str] = mapped_column(String(10), default="")
    note: Mapped[str] = mapped_column(String(40), default="")  # 예: 5분 탑승
    needs_sign: Mapped[bool] = mapped_column(Boolean, default=False)
    bus_id: Mapped[int | None] = mapped_column(ForeignKey("bus.id"), nullable=True)

    bus: Mapped[Bus | None] = relationship()


# ── 사람 ────────────────────────────────────────────────

class Teacher(Base):
    __tablename__ = "teacher"
    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(40))
    role: Mapped[str] = mapped_column(String(40), default="")
    pin_hash: Mapped[str] = mapped_column(String(200), default="")
    is_admin: Mapped[bool] = mapped_column(Boolean, default=False)
    class_id: Mapped[int | None] = mapped_column(ForeignKey("classroom.id"), nullable=True)
    active: Mapped[bool] = mapped_column(Boolean, default=True)

    classroom: Mapped[ClassRoom | None] = relationship()


class Child(Base):
    __tablename__ = "child"
    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(40))
    class_id: Mapped[int] = mapped_column(ForeignKey("classroom.id"))
    note: Mapped[str] = mapped_column(String(200), default="")  # 알레르기·투약 등
    active: Mapped[bool] = mapped_column(Boolean, default=True)

    classroom: Mapped[ClassRoom] = relationship(back_populates="children")
    guardians: Mapped[list[Guardian]] = relationship(
        back_populates="child", cascade="all, delete-orphan", order_by="Guardian.seq"
    )
    plan: Mapped[list[PlanEntry]] = relationship(
        back_populates="child", cascade="all, delete-orphan"
    )

    @property
    def default_guardian(self) -> Guardian | None:
        for g in self.guardians:
            if g.is_default:
                return g
        return self.guardians[0] if self.guardians else None


class Guardian(Base):
    """인계자. 한 아이에 여러 명을 둘 수 있고 기본은 보통 학부모다."""

    __tablename__ = "guardian"
    id: Mapped[int] = mapped_column(primary_key=True)
    child_id: Mapped[int] = mapped_column(ForeignKey("child.id"))
    name: Mapped[str] = mapped_column(String(40))
    relation: Mapped[str] = mapped_column(String(20), default="")
    phone: Mapped[str] = mapped_column(String(30), default="")
    is_default: Mapped[bool] = mapped_column(Boolean, default=False)
    seq: Mapped[int] = mapped_column(Integer, default=0)

    child: Mapped[Child] = relationship(back_populates="guardians")


# ── 주간 계획 ───────────────────────────────────────────

class PlanEntry(Base):
    """아이 × 요일 → 귀가 방법.

    round_id 가 없으면 그날은 명단에 없다 (정규 후 귀가).
    academy_id 가 있으면 학원 차량이 데려간다 → 서명 없음.
    """

    __tablename__ = "plan_entry"
    __table_args__ = (UniqueConstraint("child_id", "weekday", name="uq_plan_child_day"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    child_id: Mapped[int] = mapped_column(ForeignKey("child.id"))
    weekday: Mapped[int] = mapped_column(Integer)  # 0=월 … 4=금
    round_id: Mapped[int | None] = mapped_column(ForeignKey("round.id"), nullable=True)
    academy_id: Mapped[int | None] = mapped_column(ForeignKey("academy.id"), nullable=True)
    time_override: Mapped[str] = mapped_column(String(10), default="")

    child: Mapped[Child] = relationship(back_populates="plan")
    round: Mapped[Round | None] = relationship()
    academy: Mapped[Academy | None] = relationship()


# ── 하루 기록 ───────────────────────────────────────────

ATT_PRESENT = "출석"
ATT_ABSENT = "결석"
ATT_EARLY = "조퇴"


class Attendance(Base):
    __tablename__ = "attendance"
    __table_args__ = (UniqueConstraint("child_id", "on_date", name="uq_att_child_date"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    child_id: Mapped[int] = mapped_column(ForeignKey("child.id"))
    on_date: Mapped[dt.date] = mapped_column(Date)
    status: Mapped[str] = mapped_column(String(10), default=ATT_PRESENT)
    reason: Mapped[str] = mapped_column(String(60), default="")
    left_at: Mapped[str] = mapped_column(String(10), default="")
    teacher_id: Mapped[int | None] = mapped_column(ForeignKey("teacher.id"), nullable=True)

    child: Mapped[Child] = relationship()


DEP_WAITING = "대기"
DEP_CALLED = "호출"
DEP_DONE = "완료"


class Departure(Base):
    """귀가 처리 기록 — 인계 증빙이 되므로 지우지 않고 쌓는다."""

    __tablename__ = "departure"
    __table_args__ = (UniqueConstraint("child_id", "on_date", name="uq_dep_child_date"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    child_id: Mapped[int] = mapped_column(ForeignKey("child.id"))
    on_date: Mapped[dt.date] = mapped_column(Date)
    round_id: Mapped[int | None] = mapped_column(ForeignKey("round.id"), nullable=True)
    status: Mapped[str] = mapped_column(String(10), default=DEP_WAITING)
    called_at: Mapped[dt.datetime | None] = mapped_column(DateTime, nullable=True)
    done_at: Mapped[dt.datetime | None] = mapped_column(DateTime, nullable=True)
    handled_by: Mapped[int | None] = mapped_column(ForeignKey("teacher.id"), nullable=True)
    receiver: Mapped[str] = mapped_column(String(60), default="")   # 인계받은 사람
    how: Mapped[str] = mapped_column(String(60), default="")        # 차량 탑승 · 학원차 등
    signature: Mapped[str] = mapped_column(Text, default="")        # data:image/png;base64,…
    memo: Mapped[str] = mapped_column(String(200), default="")

    child: Mapped[Child] = relationship()
    round: Mapped[Round | None] = relationship()
    teacher: Mapped[Teacher | None] = relationship()
