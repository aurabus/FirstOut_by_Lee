"""처음 시작하는 관리자에게 무엇부터 하면 되는지 알려준다.

승인 직후 로그인하면 「오늘 현황」이 열리는데, 원아도 선생님도 없으니 빈 화면이다.
무엇을 해야 하는지 아무도 알려주지 않으면 거기서 멈춘다.

꼭 해야 할 것이 끝나면 이 안내는 저절로 사라진다. 다 해놓고도 계속 뜨면 잔소리가 된다.

선생님 초대는 **선택**이다. 총괄 관리자가 담임을 겸하는 작은 원은 혼자 쓴다.
그런 원에서 이 한 줄 때문에 안내가 영영 남으면, 그게 바로 잔소리다.
"""

from __future__ import annotations

from dataclasses import dataclass

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from . import service
from .models import ROLE_ADMIN, Child, User
from .seed import DEFAULT_CLASSES, DEFAULT_ROUNDS


@dataclass
class Step:
    key: str
    title: str
    why: str
    where: str
    done: bool
    now: str = ""      # 지금 상태 한 줄
    optional: bool = False   # 안 해도 되는 것 — 안내가 걷히는 것을 막지 않는다


def steps(db: Session, kinder_id: int) -> list[Step]:
    rooms = service.classes(db, kinder_id)
    rounds = service.rounds(db, kinder_id)

    kids = int(db.scalar(
        select(func.count(Child.id)).where(Child.kinder_id == kinder_id, Child.active.is_(True))
    ) or 0)
    teachers = int(db.scalar(
        select(func.count(User.id)).where(
            User.kinder_id == kinder_id, User.active.is_(True), User.role != ROLE_ADMIN
        )
    ) or 0)

    # 기본값 그대로면 아직 자기 원에 맞추지 않은 것으로 본다
    named = [r.name for r in rooms] != DEFAULT_CLASSES
    base_times = {name: at for _, name, _, at, _, _ in DEFAULT_ROUNDS}
    timed = any(r.at_time != base_times.get(r.name) for r in rounds)

    return [
        Step(
            "class", "반 이름 맞추기",
            "명단이 반 순서대로 나옵니다. 아이를 데리러 가는 동선대로 두시면 편합니다.",
            "/settings",
            named,
            " · ".join(r.name for r in rooms) or "반이 없습니다",
        ),
        Step(
            "round", "귀가 차수 시각 맞추기",
            "몇 시에 누가 나가는지가 여기서 정해집니다. 학기마다 바뀌면 그때 고치시면 됩니다.",
            "/settings",
            timed,
            " · ".join(f"{r.name} {r.at_time}" for r in rounds) or "차수가 없습니다",
        ),
        Step(
            "roster", "원아 명부 올리기",
            "엑셀 양식을 내려받아 채워 올리시면, 요일별 귀가 명단이 매일 자동으로 만들어집니다.",
            "/upload",
            kids > 0,
            f"{kids}명 등록" if kids else "아직 없습니다",
        ),
        Step(
            "teacher", "선생님 초대하기",
            "혼자 쓰셔도 됩니다. 함께 쓰실 분이 생기면 계정을 만들어 주세요 — "
            "QR 이 뜨고, 휴대폰으로 찍으면 그 자리에서 끝납니다.",
            "/users",
            teachers > 0,
            f"{teachers}분" if teachers else "아직 없습니다 (혼자 쓰셔도 됩니다)",
            optional=True,
        ),
    ]


def remaining(db: Session, kinder_id: int) -> list[Step]:
    """아직 안 한 것만. 비어 있으면 안내를 띄우지 않는다.

    꼭 해야 할 것이 모두 끝나면 선택 단계가 남아 있어도 안내를 접는다.
    선생님 관리는 상단바에 늘 있으므로, 나중에 사람이 늘어도 찾지 못할 일은 없다.
    """
    return progress(db, kinder_id)[0]


def progress(db: Session, kinder_id: int) -> tuple[list[Step], int, int]:
    """(보여줄 단계들, 끝낸 꼭 해야 할 것, 꼭 해야 할 것 전부)."""
    모두 = steps(db, kinder_id)
    꼭 = [s for s in 모두 if not s.optional]
    끝냄 = sum(1 for s in 꼭 if s.done)
    if 끝냄 == len(꼭):
        return [], 끝냄, len(꼭)
    return [s for s in 모두 if not s.done], 끝냄, len(꼭)
