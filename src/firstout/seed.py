"""첫 실행 때 넣는 기본 자료.

반·차수·학원은 이 유치원 기준으로 넣되, 모두 설정 화면에서 바꿀 수 있다.
원아는 시연용 가상 이름이며 `--demo` 로 넣을 때만 생성된다.
"""

from __future__ import annotations

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from .models import (
    Academy,
    Bus,
    Child,
    ClassRoom,
    Guardian,
    PlanEntry,
    Round,
    Setting,
    Teacher,
)
from .security import hash_pin

CLASS_NAMES = ["지혜1", "지혜2", "행복1", "행복2", "사랑1", "사랑2"]
ACADEMIES = ["태권도", "미술", "푸르넷", "하라온", "피아노"]

# (key, 이름, 종류, 시각, 비고, 서명여부)
ROUNDS = [
    ("i1", "1차 개별", "개별", "15:40", "", True),
    ("b1", "1차 차량", "차량", "16:00", "5분 탑승", False),
    ("b2", "2차 차량", "차량", "16:20", "5분 탑승", False),
    ("i2", "2차 개별", "개별", "16:20", "", True),
    ("care", "돌봄", "돌봄", "19:00", "저녁·온종일", True),
]


def seed_base(db: Session) -> None:
    """반·차수·학원·설정 — 비어 있을 때만 넣는다."""
    if db.scalar(select(Setting).limit(1)) is None:
        db.add(
            Setting(
                kinder_name="가득유치원",
                route_note="지혜가득 → 행복가득 → 사랑가득",
                care_close="19:00",
            )
        )

    if db.scalar(select(func.count(ClassRoom.id))) == 0:
        for i, n in enumerate(CLASS_NAMES):
            db.add(ClassRoom(name=n, seq=i))

    if db.scalar(select(func.count(Bus.id))) == 0:
        db.add(Bus(name="차량 1호", seq=0))

    if db.scalar(select(func.count(Academy.id))) == 0:
        for n in ACADEMIES:
            db.add(Academy(name=n))

    db.flush()

    if db.scalar(select(func.count(Round.id))) == 0:
        bus = db.scalar(select(Bus).order_by(Bus.seq))
        for i, (key, name, kind, at, note, sign) in enumerate(ROUNDS):
            db.add(
                Round(
                    key=key,
                    name=name,
                    kind=kind,
                    seq=i,
                    at_time=at,
                    note=note,
                    needs_sign=sign,
                    bus_id=bus.id if kind == "차량" else None,
                )
            )

    if db.scalar(select(func.count(Teacher.id))) == 0:
        db.flush()
        rooms = list(db.scalars(select(ClassRoom).order_by(ClassRoom.seq)))
        db.add(Teacher(name="원장", role="전체 관리", pin_hash=hash_pin("0000"), is_admin=True))
        for r in rooms:
            db.add(
                Teacher(
                    name=f"{r.name} 담임",
                    role=f"{r.name} 담임",
                    pin_hash=hash_pin("0000"),
                    class_id=r.id,
                )
            )
        db.add(Teacher(name="하원 도우미", role="하원 도우미", pin_hash=hash_pin("0000")))

    db.commit()


# ── 시연용 원아 ─────────────────────────────────────────

SUR = list("김이박최정강조윤장임한오서신권황안송전홍유고문양배백허남심노")
GIV = [
    "서준", "하윤", "도윤", "서연", "예준", "지우", "시우", "하은", "주원", "채원",
    "지호", "예린", "건우", "수아", "유준", "다은", "현우", "지안", "우진", "소율",
    "민재", "아린", "태양", "유나", "준서", "서아", "지훈", "하영", "승우", "예은",
    "다인", "로운", "시아", "윤슬", "해든",
]
MOM = ["박영희", "최지영", "정미경", "한소영", "임지혜", "윤가희", "서은주", "노현정"]
DAD = ["김철수", "이준영", "박태현", "오준호", "강태식", "조성민", "장민석", "신동호"]
GRAN = ["김순자", "이말순", "박옥분", "최정숙"]
SIZE = [15, 16, 16, 15, 17, 16]


def seed_demo(db: Session) -> int:
    """가상 원아와 주간 계획을 만든다. 실제 명부를 올리기 전 시연용."""
    if db.scalar(select(func.count(Child.id))):
        return 0

    rooms = list(db.scalars(select(ClassRoom).order_by(ClassRoom.seq)))
    rnds = {r.key: r for r in db.scalars(select(Round))}
    acas = list(db.scalars(select(Academy)))
    order = ["i1", "b1", "b2", "i2", "care"]

    used: set[str] = set()
    ni = 0
    made = 0

    for ci, room in enumerate(rooms):
        for i in range(SIZE[ci % len(SIZE)]):
            # 이름 만들기 (겹치지 않게)
            while True:
                name = SUR[ni % len(SUR)] + GIV[(ni * 11) % len(GIV)]
                ni += 1
                if name not in used:
                    used.add(name)
                    break

            idx = ci * 20 + i
            child = Child(name=name, class_id=room.id)
            db.add(child)
            db.flush()

            db.add(Guardian(child_id=child.id, name=MOM[idx % 8], relation="모",
                            is_default=idx % 3 != 1, seq=0))
            db.add(Guardian(child_id=child.id, name=DAD[(idx + 3) % 8], relation="부",
                            is_default=idx % 3 == 1, seq=1))
            db.add(Guardian(child_id=child.id, name=GRAN[idx % 4], relation="조모", seq=2))

            base = order[idx % len(order)]
            for wd in range(5):
                r = (idx * 7 + wd * 5) % 17
                if r == 0:
                    db.add(PlanEntry(child_id=child.id, weekday=wd))  # 그날은 정규 후 귀가
                    continue
                key = base
                if r == 1:
                    key = "i1"
                elif r == 2:
                    key = "b1"
                elif r == 3:
                    key = "care"
                elif r == 4:
                    key = "i2"
                aca = None
                if r in (6, 7) and key in ("i1", "i2") and acas:
                    aca = acas[(idx + wd) % len(acas)]
                db.add(
                    PlanEntry(
                        child_id=child.id,
                        weekday=wd,
                        round_id=rnds[key].id,
                        academy_id=aca.id if aca else None,
                        time_override="16:00" if r == 5 and key == "i1" else "",
                    )
                )
            made += 1

    db.commit()
    return made
