"""연습은 연습 자리에서만.

tools/scenario.py 는 실제 화면을 눌러 보는 도구다. 편하다는 이유로 언젠가
「그냥 돌아가는 서버에 붙이면 되지」 하고 고치고 싶어질 수 있다. 그 순간
시범 운영 중인 유치원의 자료에 연습용 아이와 선생님이 섞인다. 감사 로그와
백업에까지 남아, 지우고 싶어도 깨끗이 지워지지 않는다.

그래서 못 박아 둔다 — 이 도구는 **자기가 띄운 서버, 자기가 만든 임시 폴더**
말고는 어디도 건드리지 않는다.
"""

from __future__ import annotations

import ast
from pathlib import Path

import pytest

뿌리 = Path(__file__).resolve().parent.parent
도구 = 뿌리 / "tools" / "scenario.py"


@pytest.fixture(scope="module")
def 글() -> str:
    return 도구.read_text(encoding="utf-8")


def test_문법이_맞다(글):
    ast.parse(글)


def test_임시_폴더에만_자료를_만든다(글):
    """MAJUNG_DATA 를 반드시 새로 판 임시 폴더로 돌려놓는다."""
    assert "mkdtemp" in 글
    assert '"MAJUNG_DATA": str(자료)' in 글, "임시 폴더 말고 다른 곳을 가리키면 안 된다"


def test_끝나면_지운다(글):
    assert "rmtree" in 글
    # 윈도우는 SQLite 가 손을 놓을 때까지 잠깐 못 지운다. 한 번 시도하고
    # 「지웠습니다」라고 말하면 연습 자료가 디스크에 계속 쌓인다.
    앞 = 글.index("rmtree")
    assert "range" in 글[앞 - 200:앞], "한 번 실패하면 다시 시도해야 한다"


def test_바깥_서버는_건드리지_않는다(글):
    """주소를 밖으로 돌릴 수 있는 구멍을 두지 않는다."""
    금지 = ["aurabus.com", "192.168.", ".nas", "majung.aurabus"]
    걸린것 = [n for n in 금지 if n in 글]
    assert not 걸린것, f"연습 도구가 바깥 주소를 알고 있다: {걸린것}"
    assert "127.0.0.1" in 글, "자기가 띄운 서버에만 말을 건다"


def test_서버를_스스로_띄우고_내린다(글):
    assert "서버_띄우기" in 글
    for 무엇 in ("terminate", "kill"):
        assert 무엇 in 글, f"끝낼 때 {무엇} 로 확실히 내려야 한다"


def test_서명키는_그때그때_새로_만든다(글):
    """붙박이 키를 적어 두면 그 값이 언젠가 진짜 서버로 새어 나간다."""
    assert "random.choices" in 글 and "k=64" in 글


def test_두_가지_방법으로_부를_수_있다(글):
    """한글 자판이 안 될 때도 있다 — 영문 이름도 함께 받는다."""
    assert '"--손으로" in sys.argv' in 글
    assert '"--hand" in sys.argv' in 글


def test_배치파일이_도구를_부른다():
    배치 = 뿌리 / "try-it.bat"
    assert 배치.exists(), "두 번 눌러 쓸 수 있어야 한다"
    글 = 배치.read_text(encoding="utf-8")
    assert "tools\\scenario.py" in 글
    assert "--hand" in 글, "배치에서는 한글 없이 영문 이름으로 불러야 한다"
