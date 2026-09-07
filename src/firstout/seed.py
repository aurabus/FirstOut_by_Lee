"""유치원을 하나 만들 때 함께 넣는 기본 자료.

반 이름·차수·시각은 이 유치원 기준값일 뿐이며, 등록 후 설정 화면에서 모두 바꿀 수 있다.
원아는 시연용 가상 이름이며 따로 넣을 때만 생성된다.
"""

from __future__ import annotations

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from .models import (
    KG_ACTIVE,
    ROLE_OPERATOR,
    Academy,
    Bus,
    Child,
    ClassRoom,
    Guardian,
    Kindergarten,
    PlanEntry,
    Round,
    User,
)
from .security import hash_password

DEFAULT_CLASSES = ["지혜1", "지혜2", "행복1", "행복2", "사랑1", "사랑2"]
DEFAULT_ACADEMIES = ["태권도", "미술", "푸르넷", "하라온", "피아노"]

# (key, 이름, 종류, 시각, 비고, 서명여부)
DEFAULT_ROUNDS = [
    ("i1", "1차 개별", "개별", "15:40", "", True),
    ("b1", "1차 차량", "차량", "16:00", "5분 탑승", False),
    ("b2", "2차 차량", "차량", "16:20", "5분 탑승", False),
    ("i2", "2차 개별", "개별", "16:20", "", True),
    ("care", "돌봄", "돌봄", "19:00", "저녁·온종일", True),
]




def fill_new_kinder(
    db: Session,
    k: Kindergarten,
    class_names: list[str] | None = None,
) -> Kindergarten:
    """새 유치원에 바로 쓸 수 있는 기본 자료를 채운다.

    승인 직후 빈 화면을 마주하지 않도록 반·차수·학원을 미리 넣어두고,
    관리자가 설정 화면에서 자기 원에 맞게 고치게 한다.
    """
    for i, n in enumerate(class_names or DEFAULT_CLASSES):
        db.add(ClassRoom(kinder_id=k.id, name=n, seq=i))
    bus = Bus(kinder_id=k.id, name="차량 1호", seq=0)
    db.add(bus)
    for n in DEFAULT_ACADEMIES:
        db.add(Academy(kinder_id=k.id, name=n))
    db.flush()

    for i, (key, rname, kind, at, note, sign) in enumerate(DEFAULT_ROUNDS):
        db.add(
            Round(
                kinder_id=k.id,
                key=key,
                name=rname,
                kind=kind,
                seq=i,
                at_time=at,
                note=note,
                needs_sign=sign,
                bus_id=bus.id if kind == "차량" else None,
            )
        )

    db.flush()
    return k


def seed_operator(db: Session, login_id: str, password: str) -> User | None:
    """운영자 계정 — 서버를 세울 때 한 번 만든다."""
    if db.scalar(select(User).where(User.role == ROLE_OPERATOR)):
        return None
    u = User(
        kinder_id=None,
        login_id=login_id.strip().lower(),
        password_hash=hash_password(password),
        name="운영자",
        role=ROLE_OPERATOR,
        title="서비스 운영",
    )
    db.add(u)
    db.commit()
    return u


def seed_base(db: Session) -> None:
    """지금은 자동으로 만들 것이 없다. 유치원은 가입 신청으로만 생긴다."""
    return None


def seed_demo_kinder(db: Session, name: str = "가득유치원") -> Kindergarten:
    """시연용 유치원 — 승인까지 끝난 상태로 만든다."""
    k = db.scalar(select(Kindergarten).where(Kindergarten.name == name))
    if k:
        return k
    k = Kindergarten(
        name=name,
        route_note="지혜가득 → 행복가득 → 사랑가득",
        status=KG_ACTIVE,
        seq=(db.scalar(select(func.max(Kindergarten.seq))) or 0) + 1,
    )
    db.add(k)
    db.flush()
    fill_new_kinder(db, k)
    db.commit()
    return k


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


def seed_demo(db: Session, kinder_id: int) -> int:
    """가상 원아와 주간 계획을 만든다. 실제 명부를 올리기 전 시연용."""
    if db.scalar(select(func.count(Child.id)).where(Child.kinder_id == kinder_id)):
        return 0

    rooms = list(
        db.scalars(
            select(ClassRoom).where(ClassRoom.kinder_id == kinder_id).order_by(ClassRoom.seq)
        )
    )
    rnds = {r.key: r for r in db.scalars(select(Round).where(Round.kinder_id == kinder_id))}
    acas = list(db.scalars(select(Academy).where(Academy.kinder_id == kinder_id)))
    if not rooms or not rnds:
        return 0
    order = ["i1", "b1", "b2", "i2", "care"]

    used: set[str] = set()
    ni = 0
    made = 0

    for ci, room in enumerate(rooms):
        for i in range(SIZE[ci % len(SIZE)]):
            while True:
                name = SUR[ni % len(SUR)] + GIV[(ni * 11) % len(GIV)]
                ni += 1
                if name not in used:
                    used.add(name)
                    break

            idx = ci * 20 + i
            child = Child(kinder_id=kinder_id, name=name, class_id=room.id)
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
                    db.add(PlanEntry(child_id=child.id, weekday=wd))  # 정규 후 귀가
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
