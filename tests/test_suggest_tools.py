"""개선 요청을 읽고 답하는 도구.

선생님께 **나가는 말**을 다루는 자리라 두 가지를 못 박아 둔다.

    - 읽기와 쓰기를 나눈다. 읽기는 언제 해도 되지만 쓰기는 사람이 한 번 보고
      「그렇게 보내라」 한 뒤에만 일어나야 한다.
    - 한 줄만 고친다. 번호를 잘못 주면 아무것도 고치지 않고 멈춘다.
"""

from __future__ import annotations

import datetime as dt
import sqlite3
import subprocess
import sys
from pathlib import Path

import pytest

뿌리 = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(뿌리 / "tools"))

import reply as R  # noqa: E402


@pytest.fixture()
def 자료(tmp_path) -> Path:
    """요청 두 건이 든 임시 자료. 하나는 이미 답이 달려 있다."""
    p = tmp_path / "majung.db"
    c = sqlite3.connect(p)
    c.execute("""create table suggestion (
        id integer primary key, kinder_id integer, user_id integer,
        user_name text, kinder_name text, "where" text, body text,
        status text, created_at text, reply text, replied_at text)""")
    c.executemany(
        'insert into suggestion values (?,?,?,?,?,?,?,?,?,?,?)',
        [(1, 1, 2, "김하늘", "주덕화곡초등학교병설유치원", "귀가 명단",
          "서명 창이 작아요", "받음", str(dt.datetime.now()), "", None),
         (2, 1, 2, "이바다", "주덕화곡초등학교병설유치원", "출결 등록",
          "전체 출석 단추가 멀어요", "확인함", str(dt.datetime.now()),
          "이미 드린 답", str(dt.datetime.now()))])
    c.commit()
    c.close()
    return p


def 돌리기(자료: Path, 번호: int, 답: str, 상태: str = "확인함"):
    글 = R.쓰는글(번호, 답, 상태, str(자료))
    return subprocess.run([sys.executable, "-"], input=글, capture_output=True,
                          text=True, encoding="utf-8", errors="replace")


def 읽기(자료: Path, 번호: int):
    c = sqlite3.connect(자료)
    r = c.execute("select status, reply, replied_at from suggestion where id = ?",
                  (번호,)).fetchone()
    c.close()
    return r


def test_답이_달린다(자료):
    난 = 돌리기(자료, 1, "서명 창을 키웠습니다. 다음 판에 반영됩니다.", "반영됨")
    assert 난.returncode == 0, 난.stdout + 난.stderr
    상태, 답, 때 = 읽기(자료, 1)
    assert 상태 == "반영됨"
    assert 답 == "서명 창을 키웠습니다. 다음 판에 반영됩니다."
    assert 때, "답한 때가 있어야 화면이 「언제 답했는지」를 보여준다"


def test_보내신_말을_먼저_보여준다(자료):
    """엉뚱한 요청에 답하고 있는 것은 아닌지, 쓰기 전에 눈으로 본다."""
    난 = 돌리기(자료, 1, "네 확인했습니다")
    assert "김하늘" in 난.stdout
    assert "서명 창이 작아요" in 난.stdout


def test_이미_답이_있으면_알려준다(자료):
    난 = 돌리기(자료, 2, "다시 드리는 답")
    assert "이미 답이 달려 있습니다" in 난.stdout
    assert "덮어씁니다" in 난.stdout
    assert 읽기(자료, 2)[1] == "다시 드리는 답"


def test_없는_번호면_아무것도_안_고친다(자료):
    난 = 돌리기(자료, 99, "엉뚱한 답")
    assert 난.returncode != 0
    assert 읽기(자료, 1)[1] == "", "다른 요청이 건드려졌다"
    assert 읽기(자료, 2)[1] == "이미 드린 답"


def test_한글과_따옴표가_그대로_간다(자료):
    """따옴표 하나에 글이 잘려 나가면 선생님이 이상한 답을 받으신다."""
    말 = '「서명」 창을 키웠습니다 — \'가로 2배\' 로 넓혔고, "확인" 단추도 크게 했습니다.\n줄바꿈도 됩니다.'
    난 = 돌리기(자료, 1, 말)
    assert 난.returncode == 0, 난.stdout + 난.stderr
    assert 읽기(자료, 1)[1] == 말


def test_상태는_정해진_것만_쓴다():
    """화면이 아는 말이어야 한다 — 모르는 말을 넣으면 표시가 깨진다."""
    from firstout.models import SUG_STATES

    assert R.상태들 == SUG_STATES


def test_읽는_도구는_아무것도_안_고친다():
    글 = (뿌리 / "tools" / "suggestions.py").read_text(encoding="utf-8")
    assert "mode=ro" in 글, "읽기 전용으로 열어야 한다"
    for 위험한것 in ("update ", "delete ", "insert ", "commit("):
        assert 위험한것 not in 글.lower(), f"읽는 도구에 {위험한것} 이 있다"
