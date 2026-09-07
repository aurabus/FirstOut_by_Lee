"""데이터 구조.

핵심 설계
- 회사 서버 한 곳에서 **여러 유치원**에 서비스한다. 반·차량·차수·학원·계정·원아는 모두
  유치원(Kindergarten)에 속하며, 조회는 언제나 유치원 단위로 걸러진다.
- 계정은 셋으로 나뉜다. 운영자(우리)·원장(유치원 관리자)·교사.
  유치원 가입은 원장만 신청하고 운영자가 승인하며, 교사 계정은 원장이 만든다.
- 아이의 귀가 방법은 "아이 × 요일" 단위(PlanEntry)로 저장한다. 요일마다 다르기 때문.
- 하루치 기록(Attendance·Departure)은 날짜별로 따로 쌓아 과거를 그대로 보존한다.
"""

from __future__ import annotations

import datetime as dt
import re

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


# ── 유치원 ──────────────────────────────────────────────

KG_PENDING = "승인대기"
KG_ACTIVE = "이용중"
KG_SUSPENDED = "정지"


class Kindergarten(Base):
    """서비스를 쓰는 유치원 한 곳. 아래 모든 자료의 주인이다.

    원장이 가입을 신청하면 승인대기 상태로 만들어지고, 운영자가 승인해야 쓸 수 있다.
    """

    __tablename__ = "kindergarten"
    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(60), unique=True)
    route_note: Mapped[str] = mapped_column(String(120), default="")
    status: Mapped[str] = mapped_column(String(10), default=KG_PENDING)
    phone: Mapped[str] = mapped_column(String(30), default="")
    memo: Mapped[str] = mapped_column(String(200), default="")   # 운영자 메모
    seq: Mapped[int] = mapped_column(Integer, default=0)
    created_at: Mapped[dt.datetime] = mapped_column(DateTime, default=dt.datetime.now)
    approved_at: Mapped[dt.datetime | None] = mapped_column(DateTime, nullable=True)

    @property
    def usable(self) -> bool:
        return self.status == KG_ACTIVE


# ── 설정 자료 (유치원별) ────────────────────────────────

class ClassRoom(Base):
    """반. seq 순서가 곧 아이를 데려오는 동선 순서다."""

    __tablename__ = "classroom"
    __table_args__ = (UniqueConstraint("kinder_id", "name", name="uq_class_kinder_name"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    kinder_id: Mapped[int] = mapped_column(ForeignKey("kindergarten.id"))
    name: Mapped[str] = mapped_column(String(40))
    seq: Mapped[int] = mapped_column(Integer, default=0)

    children: Mapped[list[Child]] = relationship(back_populates="classroom")


class Bus(Base):
    __tablename__ = "bus"
    __table_args__ = (UniqueConstraint("kinder_id", "name", name="uq_bus_kinder_name"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    kinder_id: Mapped[int] = mapped_column(ForeignKey("kindergarten.id"))
    name: Mapped[str] = mapped_column(String(40))
    seq: Mapped[int] = mapped_column(Integer, default=0)


class Academy(Base):
    __tablename__ = "academy"
    __table_args__ = (UniqueConstraint("kinder_id", "name", name="uq_aca_kinder_name"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    kinder_id: Mapped[int] = mapped_column(ForeignKey("kindergarten.id"))
    name: Mapped[str] = mapped_column(String(40))


class Round(Base):
    """귀가 차수.

    kind 는 처리 방식을 가른다.
      개별 = 사람에게 건넴 → 서명
      차량 = 차에 태움     → 체크만
      돌봄 = 사람에게 건넴 → 서명
    학원차로 가는 아이는 개별 차수에 함께 나가지만 서명은 받지 않는다.
    """

    __tablename__ = "round"
    __table_args__ = (UniqueConstraint("kinder_id", "key", name="uq_round_kinder_key"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    kinder_id: Mapped[int] = mapped_column(ForeignKey("kindergarten.id"))
    key: Mapped[str] = mapped_column(String(20))
    name: Mapped[str] = mapped_column(String(40))
    kind: Mapped[str] = mapped_column(String(10))  # 개별 · 차량 · 돌봄
    seq: Mapped[int] = mapped_column(Integer, default=0)
    at_time: Mapped[str] = mapped_column(String(10), default="")
    note: Mapped[str] = mapped_column(String(40), default="")  # 예: 5분 탑승
    needs_sign: Mapped[bool] = mapped_column(Boolean, default=False)
    bus_id: Mapped[int | None] = mapped_column(ForeignKey("bus.id"), nullable=True)

    bus: Mapped[Bus | None] = relationship()


# ── 사람 ────────────────────────────────────────────────

ROLE_OPERATOR = "운영자"   # 우리 회사 — 유치원 가입 승인
ROLE_OWNER = "원장"        # 유치원 관리자 — 선생님 계정과 설정을 맡는다
ROLE_TEACHER = "교사"


class User(Base):
    """로그인 계정.

    아이디는 서비스 전체에서 유일하다. 유치원을 고르는 화면 없이
    아이디 하나로 어느 유치원 사람인지 정해지므로 로그인이 한 단계 짧아지고,
    무엇보다 유치원 목록과 선생님 명단이 밖으로 드러나지 않는다.
    """

    __tablename__ = "user"
    id: Mapped[int] = mapped_column(primary_key=True)
    kinder_id: Mapped[int | None] = mapped_column(
        ForeignKey("kindergarten.id"), nullable=True
    )   # 운영자는 특정 유치원에 속하지 않는다
    login_id: Mapped[str] = mapped_column(String(40), unique=True)
    password_hash: Mapped[str] = mapped_column(String(200), default="")
    name: Mapped[str] = mapped_column(String(40))
    role: Mapped[str] = mapped_column(String(10), default=ROLE_TEACHER)
    title: Mapped[str] = mapped_column(String(40), default="")   # 화면에 보일 직함
    email: Mapped[str] = mapped_column(String(80), default="")
    phone: Mapped[str] = mapped_column(String(30), default="")
    class_id: Mapped[int | None] = mapped_column(ForeignKey("classroom.id"), nullable=True)
    active: Mapped[bool] = mapped_column(Boolean, default=True)
    must_change_pw: Mapped[bool] = mapped_column(Boolean, default=False)
    failed_count: Mapped[int] = mapped_column(Integer, default=0)
    locked_until: Mapped[dt.datetime | None] = mapped_column(DateTime, nullable=True)
    last_login_at: Mapped[dt.datetime | None] = mapped_column(DateTime, nullable=True)
    created_at: Mapped[dt.datetime] = mapped_column(DateTime, default=dt.datetime.now)

    classroom: Mapped[ClassRoom | None] = relationship()
    kinder: Mapped[Kindergarten | None] = relationship()

    @property
    def is_operator(self) -> bool:
        return self.role == ROLE_OPERATOR

    @property
    def is_admin(self) -> bool:
        """유치원 설정을 만질 수 있는 사람."""
        return self.role in (ROLE_OWNER, ROLE_OPERATOR)


class Child(Base):
    __tablename__ = "child"
    id: Mapped[int] = mapped_column(primary_key=True)
    kinder_id: Mapped[int] = mapped_column(ForeignKey("kindergarten.id"))
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
    """인계자. 한 아이에 여러 명을 둘 수 있고 기본은 보통 학부모다.

    연락처는 결석 확인 전화에 필요해 저장하지만 화면에는 가려서 보여준다.
    이름만으로는 그 자체로 개인을 특정하기 어렵지만, 이름과 전화번호가 함께
    화면에 떠 있으면 사진 한 장으로 유출된다.
    """

    __tablename__ = "guardian"
    id: Mapped[int] = mapped_column(primary_key=True)
    child_id: Mapped[int] = mapped_column(ForeignKey("child.id"))
    name: Mapped[str] = mapped_column(String(40))
    relation: Mapped[str] = mapped_column(String(20), default="")
    phone: Mapped[str] = mapped_column(String(30), default="")
    is_default: Mapped[bool] = mapped_column(Boolean, default=False)
    seq: Mapped[int] = mapped_column(Integer, default=0)

    child: Mapped[Child] = relationship(back_populates="guardians")

    @property
    def phone_masked(self) -> str:
        """가운데만 가린다. 뒤 네 자리로 본인 확인은 되고 옮겨 적을 수는 없다.

        010-1234-5678 → 010-****-5678
        02-123-4567   → 02-***-4567
        """
        raw = self.phone.strip()
        if not raw:
            return ""
        parts = [p for p in re.split(r"[^0-9]+", raw) if p]
        if len(parts) >= 3:
            return f"{parts[0]}-{'*' * len(parts[1])}-{parts[-1]}"
        digits = "".join(parts)
        if len(digits) < 7:
            return "*" * len(digits)
        return f"{digits[:3]}-{'*' * (len(digits) - 7)}-{digits[-4:]}"

    @property
    def has_phone(self) -> bool:
        return bool(self.phone.strip())


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
    teacher_id: Mapped[int | None] = mapped_column(ForeignKey("user.id"), nullable=True)

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
    handled_by: Mapped[int | None] = mapped_column(ForeignKey("user.id"), nullable=True)
    receiver: Mapped[str] = mapped_column(String(60), default="")   # 인계받은 사람
    how: Mapped[str] = mapped_column(String(60), default="")        # 차량 탑승 · 학원차 등
    signature: Mapped[str] = mapped_column(Text, default="")        # data:image/png;base64,…
    memo: Mapped[str] = mapped_column(String(200), default="")

    child: Mapped[Child] = relationship()
    round: Mapped[Round | None] = relationship()
    teacher: Mapped[User | None] = relationship()
