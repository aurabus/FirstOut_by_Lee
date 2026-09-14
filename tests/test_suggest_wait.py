"""답을 기다리는 동안 화면이 하는 말.

보내고 나면 상태가 「받음」인 채로 멈춰 있었다. 그러면 보낸 분은 **아무도 안
보고 있다**고 느끼신다. 실제로는 보고 있어도 그렇다.

이 말은 우리 세션과 무관하게 화면이 스스로 한다 — 사람이 기다리는 자리를
「내가 켜져 있어야 도는 것」에 걸어두면 안 되기 때문이다.
"""

from __future__ import annotations

import datetime as dt

import pytest

from firstout.models import Suggestion


def 요청(전에: dt.timedelta, 답: str = "") -> Suggestion:
    return Suggestion(created_at=dt.datetime.now() - 전에, body="시험", reply=답)


def test_방금_보냈으면_접수됐다고_한다():
    말, 결 = 요청(dt.timedelta(minutes=3)).waiting
    assert "접수" in 말
    assert "하루 안에" in 말
    assert 결 == "ok"


def test_몇_시간_지나면_얼마나_기다렸는지_말한다():
    말, 결 = 요청(dt.timedelta(hours=5)).waiting
    assert "5시간" in 말
    assert "오늘 안에" in 말
    assert 결 == "ok"


def test_하루가_넘으면_말을_바꾼다():
    """기다리게 해놓고 「곧 드립니다」를 그대로 두면 그게 더 무례하다."""
    말, 결 = 요청(dt.timedelta(days=2, hours=1)).waiting
    assert "2일째" in 말
    assert "죄송" in 말
    assert 결 == "late", "늦은 것은 눈에 띄어야 한다"


def test_답이_달리면_기다림_문구는_사라진다():
    말, 결 = 요청(dt.timedelta(days=3), 답="고쳤습니다").waiting
    assert 말 == "" and 결 == ""


def test_보낸_때가_없어도_터지지_않는다():
    """자료가 옛날 것이면 비어 있을 수 있다. 화면이 죽을 일은 아니다."""
    s = Suggestion(body="시험", reply="")
    말, 결 = s.waiting
    assert 말 and 결 == "ok"


@pytest.mark.parametrize("얼마", [
    dt.timedelta(minutes=1), dt.timedelta(hours=1), dt.timedelta(hours=23),
    dt.timedelta(days=1), dt.timedelta(days=30),
])
def test_어느_때든_할_말이_있다(얼마):
    말, 결 = 요청(얼마).waiting
    assert 말, "빈 칸이 뜨면 안 된다"
    assert 결 in ("ok", "late")


def test_화면이_그_말을_보여준다():
    from pathlib import Path

    import firstout

    html = (Path(firstout.__file__).parent / "templates" / "suggest.html").read_text(
        encoding="utf-8")
    assert "r.waiting" in html
    assert "sug-wait" in html


def test_문구_모음이_있다():
    """제가 그때그때 지어내면 지킬 수 없는 약속이 나간다."""
    from pathlib import Path

    p = Path(__file__).resolve().parent.parent / "docs" / "답변-문구.md"
    assert p.exists(), "docs/답변-문구.md 가 없다"
    글 = p.read_text(encoding="utf-8")
    for 있어야할것 in ("접수", "사용법", "오류", "기능 요청", "쓰지 않는 말"):
        assert 있어야할것 in 글, f"문구 모음에 「{있어야할것}」 대목이 없다"
