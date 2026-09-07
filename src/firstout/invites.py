"""첫 로그인 초대 — 1회용, 10분, 그 선생님 한 사람 전용.

관리자가 계정을 만들면 임시 비밀번호를 선생님께 전해야 하는데, 카카오톡으로 보내면
**그 방에 계속 남는다.** 나중에 그 방을 보는 누구나 쓸 수 있다.

대신 관리자가 화면에 QR 을 띄우고 선생님이 자기 휴대폰으로 찍게 한다.
어디에도 남지 않고, 한 번 쓰면 사라지고, 10분이 지나면 저절로 죽는다.
새어 나가더라도 10분 · 한 번 · 계정 하나로 피해가 갇힌다.

원문은 저장하지 않는다. 표에는 대조용 표식만 둔다.
"""

from __future__ import annotations

import datetime as dt
import hashlib
import secrets

from sqlalchemy import delete, select
from sqlalchemy.orm import Session

from .config import PUBLIC_URL
from .models import Invite, User

MINUTES = 10          # 두 사람이 마주 보고 있는 동안만 살아 있으면 된다
KEEP_DAYS = 7         # 다 쓴 기록은 이만큼만 두고 지운다


def fingerprint(token: str) -> str:
    return hashlib.sha256(token.encode()).hexdigest()


def issue(db: Session, user: User, by: User | None, at: dt.datetime) -> str:
    """새 초대를 만들고 **원문을 돌려준다** — 돌려준 이 값은 다시 볼 수 없다.

    같은 선생님에게 아직 살아 있는 초대가 있으면 함께 죽인다.
    두 개가 동시에 돌아다니면 어느 것이 새어 나갔는지 알 수 없다.
    """
    db.execute(delete(Invite).where(Invite.user_id == user.id, Invite.used_at.is_(None)))

    token = secrets.token_urlsafe(24)
    db.add(
        Invite(
            user_id=user.id,
            token_hash=fingerprint(token),
            made_by=by.id if by else None,
            created_at=at,
            expires_at=at + dt.timedelta(minutes=MINUTES),
        )
    )
    db.commit()
    return token


def find(db: Session, token: str, at: dt.datetime) -> Invite | None:
    """살아 있는 초대만 돌려준다."""
    if not token:
        return None
    inv = db.scalar(select(Invite).where(Invite.token_hash == fingerprint(token)))
    return inv if inv and inv.alive(at) else None


def use(db: Session, inv: Invite, at: dt.datetime) -> None:
    inv.used_at = at
    db.commit()


def link(token: str, request=None) -> str:
    """선생님이 찍을 주소. 서비스 주소가 정해져 있으면 그것을 쓴다."""
    base = PUBLIC_URL
    if not base and request is not None:
        base = str(request.base_url).rstrip("/")
    return f"{base}/join/{token}"


def sweep(db: Session, at: dt.datetime | None = None, keep_days: int = KEEP_DAYS) -> int:
    """다 쓴 것과 기한 지난 것을 치운다."""
    at = at or dt.datetime.now()
    cutoff = at - dt.timedelta(days=keep_days)
    old = (Invite.expires_at < cutoff) | (Invite.used_at < cutoff)
    rows = list(db.scalars(select(Invite.id).where(old)))
    if rows:
        db.execute(delete(Invite).where(Invite.id.in_(rows)))
        db.commit()
    return len(rows)
