"""감사 로그 — 누가 언제 무엇을 했는지.

아이를 데려가는 권한이 걸린 시스템이라 "그때 누가 눌렀나"를 되짚을 수 있어야 한다.
화면을 연 것까지 모두 남기되, **한 달이 지나면 자동으로 지운다.** 오래 쌓아둘수록
새어 나갔을 때의 피해만 커지기 때문이다.

기록에 개인정보를 담지 않는다. 원아 이름은 주소에 실리지 않고(안내문은 쿠키로 간다),
남는 것은 무엇을 했는지와 대상의 번호뿐이다.
"""

from __future__ import annotations

import datetime as dt
import re

from sqlalchemy import delete, select
from sqlalchemy.orm import Session

from .models import AuditLog, User
from .security import read_token

KEEP_DAYS = 30

# 기록하지 않는 것 — 남겨봐야 의미가 없고 양만 늘린다
SKIP_EXACT = {"/health", "/favicon.ico", "/sw.js"}
SKIP_PREFIX = ("/static/",)

# 주소를 사람이 읽을 수 있는 말로 바꾼다
ACTIONS: list[tuple[re.Pattern[str], str]] = [
    (re.compile(r"^/signin$"), "로그인"),
    (re.compile(r"^/signout$"), "로그아웃"),
    (re.compile(r"^/signup"), "가입 신청"),
    (re.compile(r"^/me/password$"), "비밀번호 변경"),
    (re.compile(r"^/board"), "오늘 현황"),
    (re.compile(r"^/attend/all/\d+$"), "출결 · 전체 출석 처리"),
    (re.compile(r"^/attend/\d+$"), "출결 · 출석 상태 변경"),
    (re.compile(r"^/attend"), "출결 등록"),
    (re.compile(r"^/roster/export$"), "원아 명부 엑셀 내려받기"),
    (re.compile(r"^/roster/add$"), "원아 등록"),
    (re.compile(r"^/child/\d+/plan$"), "원아 · 주간 계획 수정"),
    (re.compile(r"^/child/\d+/guardian"), "원아 · 인계자 수정"),
    (re.compile(r"^/child/\d+/leave$"), "원아 · 퇴원 처리"),
    (re.compile(r"^/child/\d+/save$"), "원아 · 정보 수정"),
    (re.compile(r"^/child/"), "원아 상세"),
    (re.compile(r"^/roster"), "원아 명부"),
    (re.compile(r"^/list/[^/]+/\d+/sign$"), "귀가 · 서명 인계"),
    (re.compile(r"^/list/[^/]+/\d+/check$"), "귀가 · 탑승 체크"),
    (re.compile(r"^/list/[^/]+/\d+/undo$"), "귀가 · 처리 취소"),
    (re.compile(r"^/list/[^/]+/\d+/memo$"), "귀가 · 특이사항"),
    (re.compile(r"^/list/"), "귀가 명단"),
    (re.compile(r"^/users/add$"), "선생님 계정 추가"),
    (re.compile(r"^/users/\d+/reset$"), "선생님 비밀번호 재발급"),
    (re.compile(r"^/users/\d+/invite$"), "선생님 초대 발급"),
    (re.compile(r"^/users/\d+/toggle$"), "선생님 사용·중지"),
    (re.compile(r"^/users/\d+/save$"), "선생님 정보 수정"),
    (re.compile(r"^/users"), "선생님 관리"),
    (re.compile(r"^/settings/class"), "설정 · 반"),
    (re.compile(r"^/settings/bus"), "설정 · 차량"),
    (re.compile(r"^/settings/round"), "설정 · 귀가 차수"),
    (re.compile(r"^/settings/academy"), "설정 · 학원"),
    (re.compile(r"^/settings/kinder"), "설정 · 유치원 정보"),
    (re.compile(r"^/settings"), "설정"),
    (re.compile(r"^/upload"), "명부 엑셀"),
    (re.compile(r"^/operator/\d+/approve$"), "유치원 승인"),
    (re.compile(r"^/operator/\d+/suspend$"), "유치원 중지"),
    (re.compile(r"^/operator/\d+/reject$"), "가입 신청 거절·삭제"),
    (re.compile(r"^/operator"), "유치원 운영"),
    (re.compile(r"^/audit"), "감사 로그"),
    (re.compile(r"^/connect"), "접속 안내"),
    (re.compile(r"^/help"), "사용 안내"),
    (re.compile(r"^/suggest/\d+/reply$"), "개선 요청 답변"),
    (re.compile(r"^/suggest"), "개선 요청"),
    (re.compile(r"^/$"), "첫 화면"),
    (re.compile(r"^/(login|pick)$"), "옛 주소"),
    (re.compile(r"^/join/"), "초대로 첫 로그인"),
    (re.compile(r"^/reauth"), "본인 확인"),
]

# 주소 자체가 비밀인 것들 — 기록에 원문을 남기면 한 달 동안 열쇠가 굴러다닌다
SECRET_PREFIXES = ("/join/",)


def mask(path: str) -> str:
    """비밀이 담긴 주소는 앞부분만 남긴다."""
    for head in SECRET_PREFIXES:
        if path.startswith(head):
            return head + "…"
    return path


UNKNOWN = "그 밖의 화면"


def describe(path: str) -> str:
    """주소를 사람이 읽는 말로. 영문 주소를 그대로 보여주지 않는다.

    선생님이 「/attend」 를 보고 무슨 일인지 알 수는 없다. 새 화면이 늘어나면
    여기에 함께 적어야 하고, 빠뜨리지 않도록 시험으로 묶어 두었다.
    """
    for pat, label in ACTIONS:
        if pat.match(path):
            return label
    return UNKNOWN


def should_log(path: str) -> bool:
    return path not in SKIP_EXACT and not path.startswith(SKIP_PREFIX)


def write(
    db: Session,
    *,
    user: User | None,
    method: str,
    path: str,
    status: int,
    ip: str = "",
    agent: str = "",
    detail: str = "",
) -> None:
    db.add(
        AuditLog(
            at=dt.datetime.now(),
            user_id=user.id if user else None,
            # 계정이 지워지거나 이름이 바뀌어도 그때의 사람을 알 수 있게 함께 적어둔다
            user_name=user.name if user else "",
            kinder_id=user.kinder_id if user else None,
            method=method,
            path=mask(path)[:200],
            action=describe(path),
            status=status,
            ip=ip[:45],
            agent=agent[:120],
            detail=detail[:200],
        )
    )
    db.commit()


def user_from_cookie(db: Session, cookie: str | None) -> User | None:
    got = read_token(cookie)
    if got is None:
        return None
    return db.get(User, got[0])


def purge_old(db: Session, keep_days: int = KEEP_DAYS) -> int:
    """한 달 지난 기록을 지운다."""
    cutoff = dt.datetime.now() - dt.timedelta(days=keep_days)
    n = len(list(db.scalars(select(AuditLog.id).where(AuditLog.at < cutoff))))
    if n:
        db.execute(delete(AuditLog).where(AuditLog.at < cutoff))
        db.commit()
    return n


# ── 결과를 사람 말로 ────────────────────────────────────

def outcome(method: str, status: int, has_user: bool, path: str = "") -> tuple[str, str]:
    """(보여줄 말, 색 이름). 숫자만 보고 무슨 일인지 알 수는 없다."""
    if status >= 500:
        return ("서버 오류", "bad")
    if status >= 400:
        return ("막힘", "bad")
    if method == "POST" and path.startswith("/signin") and not has_user:
        # 로그인은 되든 안 되든 303 이라 숫자로는 구분되지 않는다.
        # 성공한 로그인에는 그 사람이 붙으므로, 붙지 않았으면 실패다.
        return ("로그인 실패", "bad")
    if status >= 300:
        # 화면을 열었는데 다른 곳으로 갔다면 처리한 것이 아니라 넘어간 것이다
        return ("처리됨", "ok") if method == "POST" else ("넘어감", "plain")
    return ("열어봄", "plain")
