"""처음 시작하는 원장에게 무엇부터 하면 되는지 알려준다.

승인 직후 로그인하면 「오늘 현황」이 열리는데, 원아도 선생님도 없으니 빈 화면이다.
무엇을 해야 하는지 아무도 알려주지 않으면 거기서 멈춘다.

네 가지가 끝나면 이 안내는 저절로 사라진다. 다 해놓고도 계속 뜨면 잔소리가 된다.
"""

from __future__ import annotations

from dataclasses import dataclass

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from . import service
from .models import Child, User
from .seed import DEFAULT_CLASSES, DEFAULT_ROUNDS


@dataclass
class Step:
    key: str
    title: str
    why: str
    where: str
    done: bool
    now: str = ""      # 지금 상태 한 줄


def steps(db: Session, kinder_id: int) -> list[Step]:
    rooms = service.classes(db, kinder_id)
    rounds = service.rounds(db, kinder_id)

    kids = int(db.scalar(
        select(func.count(Child.id)).where(Child.kinder_id == kinder_id, Child.active.is_(True))
    ) or 0)
    teachers = int(db.scalar(
        select(func.count(User.id)).where(
            User.kinder_id == kinder_id, User.active.is_(True), User.role != "원장"
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
            "계정을 만들면 QR 이 뜹니다. 선생님 휴대폰으로 찍게 하시면 그 자리에서 끝납니다.",
            "/users",
            teachers > 0,
            f"{teachers}분" if teachers else "아직 없습니다",
        ),
    ]


def remaining(db: Session, kinder_id: int) -> list[Step]:
    """아직 안 한 것만. 비어 있으면 안내를 띄우지 않는다."""
    return [s for s in steps(db, kinder_id) if not s.done]
