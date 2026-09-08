"""개선 요청.

쓰다가 불편한 순간은 그 화면을 보고 있을 때다. 그때 바로 보낼 수 있어야 하고,
**어느 화면에서 보냈는지가 함께 담겨야** 우리가 알아들을 수 있다.
「명단이 불편해요」와 「귀가 명단에서 불편해요」는 다른 이야기다.
"""

from __future__ import annotations

import pytest
from sqlalchemy import create_engine, select
from sqlalchemy.orm import sessionmaker

from firstout import audit
from firstout.models import (
    SUG_DONE,
    SUG_NEW,
    SUG_STATES,
    Base,
    Kindergarten,
    Suggestion,
)

KID = 1


@pytest.fixture()
def db():
    engine = create_engine("sqlite://")
    Base.metadata.create_all(engine)
    s = sessionmaker(bind=engine)()
    s.add_all([
        Kindergarten(id=KID, name="가유치원", status="이용중"),
        Kindergarten(id=2, name="나유치원", status="이용중"),
    ])
    s.commit()
    yield s
    s.close()


def _send(s, kinder_id=KID, where="귀가 명단", body="아이 찾기가 어려워요", who="김미영"):
    x = Suggestion(kinder_id=kinder_id, user_name=who, kinder_name="가유치원",
                   where=where, body=body)
    s.add(x)
    s.commit()
    return x


def test_어느_화면에서_보냈는지가_함께_담긴다(db):
    x = _send(db)
    assert x.where == "귀가 명단"
    assert x.status == SUG_NEW
    assert not x.answered


def test_화면_이름은_주소가_아니라_사람이_읽는_말이다():
    """감사 로그와 같은 이름표를 쓴다 — 「/attend」 라고 적히면 아무도 못 알아본다."""
    for path, want in (("/attend", "출결 등록"), ("/list/i1", "귀가 명단"),
                       ("/roster", "원아 명부"), ("/child/3", "원아 상세")):
        got = audit.describe(path)
        assert got == want
        assert "/" not in got


def test_답이_달리면_보인다(db):
    x = _send(db)
    x.reply = "다음 주에 찾기 칸을 넣겠습니다"
    x.status = SUG_DONE
    db.commit()
    assert x.answered
    assert x.status in SUG_STATES


def test_남의_유치원_요청은_섞이지_않는다(db):
    """한 번 설치해 여러 유치원이 쓴다. 남의 원 요청이 보이면 안 된다."""
    _send(db, kinder_id=KID, body="가유치원 요청")
    _send(db, kinder_id=2, body="나유치원 요청")

    mine = list(db.scalars(select(Suggestion).where(Suggestion.kinder_id == KID)))
    assert [x.body for x in mine] == ["가유치원 요청"]
    everything = list(db.scalars(select(Suggestion)))
    assert len(everything) == 2          # 운영자는 모두 본다


def test_보낸_사람_이름을_함께_남긴다(db):
    """계정이 바뀌어도 누가 말했는지 알아야 되물어볼 수 있다."""
    x = _send(db, who="박선생")
    assert x.user_name == "박선생"
    assert x.kinder_name == "가유치원"


def test_모든_화면에서_보낼_수_있다():
    """화면마다 따로 넣으면 언젠가 빠뜨린다. base 한 곳에서 붙인다."""
    from pathlib import Path

    import firstout

    root = Path(firstout.__file__).parent / "templates"
    base = (root / "base.html").read_text(encoding="utf-8")
    assert 'id="askOpen"' in base
    assert 'action="/suggest"' in base
    assert 'name="page" value="{{ request.url.path }}"' in base

    # 화면마다 중복해서 넣지 않았는지
    dup = [f.stem for f in root.glob("*.html")
           if f.stem != "base" and 'id="askOpen"' in f.read_text(encoding="utf-8")]
    assert dup == [], f"화면에 따로 넣은 곳: {dup}"
