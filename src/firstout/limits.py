"""너무 잦은 요청을 막는다.

주소가 공개된 서비스라 가입 신청 창구가 밖으로 열려 있다. 승인제라 실제로
들어오지는 못하지만, **신청 한 번에 유치원·반·차수·계정이 스무 줄쯤 만들어진다.**
그대로 두면 운영 화면이 쓰레기로 덮이고 자료가 부풀어 오른다.

세는 값은 감사 로그를 그대로 쓴다. 어차피 모든 요청이 거기 남으므로
따로 표를 만들 이유가 없고, 서버를 다시 켜도 셈이 이어진다.

로그인은 여기서 막지 않는다. 한 유치원의 선생님들이 같은 공유기를 쓰기 때문에
주소 하나로 세면 **원 전체가 함께 잠긴다.** 로그인은 계정별 잠금(5회·10분)으로 막는다.
"""

from __future__ import annotations

import datetime as dt

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from .models import AuditLog

# (횟수, 분) — 진짜 신청하는 분이 걸릴 일이 없을 만큼 넉넉하게 둔다.
# 유치원 하나가 가입하는 일은 평생 한 번이다.
SIGNUP_IP_HOUR = (3, 60)
SIGNUP_IP_DAY = (5, 60 * 24)
SIGNUP_ALL_HOUR = (20, 60)      # 여러 주소로 나눠 들어오는 경우까지


def count(db: Session, path: str, minutes: int, ip: str = "", method: str = "POST") -> int:
    """최근 이만큼 사이에 그 길로 들어온 횟수."""
    since = dt.datetime.now() - dt.timedelta(minutes=minutes)
    q = select(func.count(AuditLog.id)).where(
        AuditLog.path == path, AuditLog.method == method, AuditLog.at >= since
    )
    if ip:
        q = q.where(AuditLog.ip == ip)
    return int(db.scalar(q) or 0)


def signup_blocked(db: Session, ip: str) -> str:
    """막아야 하면 안내문을, 통과시켜도 되면 빈 문자열을 돌려준다."""
    for limit, minutes in (SIGNUP_IP_HOUR, SIGNUP_IP_DAY):
        if ip and count(db, "/signup", minutes, ip=ip) >= limit:
            return (
                "가입 신청이 너무 잦습니다. 잠시 후 다시 시도해 주시고, "
                "급하시면 전화로 알려주세요."
            )

    limit, minutes = SIGNUP_ALL_HOUR
    if count(db, "/signup", minutes) >= limit:
        return "지금은 가입 신청이 몰려 있습니다. 잠시 후 다시 시도해 주세요."
    return ""
