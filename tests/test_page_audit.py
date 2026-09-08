"""화면 전수 점검기가 무뎌지지 않았는지 본다.

검사기가 아무것도 못 찾으면 「이상 없음」이라고 말한다. 그 말이 참인지 거짓인지는
검사기를 믿을 수 있을 때만 뜻이 있다. 그래서 일부러 망친 화면을 하나 만들어 두고,
망친 곳을 모두 짚어내는지 확인한다.

실제로 처음 만든 검사기는 태그를 정규식으로 걷어내다가 글 속 부등호에 밀려
상단바의 주소를 「사람 눈에 보이는 영문 주소」로 잘못 짚었다.
"""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "tools"))

import page_audit as A  # noqa: E402

망친화면 = """<html><head><title></title></head><body>
<table><thead><tr><th>가</th><th colspan="3">나</th></tr>
<tr><th>다</th><th>라</th></tr></thead>
<tbody><tr><td>1</td><td>2</td><td>3</td></tr></tbody></table>
<div id="같음"></div><div id="같음"></div>
<label for="없는칸">이름</label>
<span class="이런클래스는없다">x</span>
<form method="post" action="/settings/kinder"><button>저장</button></form>
<form method="post" action="/a"><form method="post" action="/b"></form></form>
<img src="https://cdn.example.com/x.png">
<a href="/x"></a>
<p>기록: /attend 를 열었습니다</p>
<div>
</body></html>"""


@pytest.fixture(scope="module")
def 걸린것() -> str:
    return "\n".join(A.살펴보기("시험", "/망친화면", 망친화면, A.css_클래스()))


@pytest.mark.parametrize("무엇", [
    "표의 칸 수가 줄마다 다르다",
    "닫히지 않은 태그",
    "같은 id 가 두 번 이상",
    "없는 id 를 가리킨다",
    "CSS 에 없는 class",
    "바깥 자원을 부른다",
    "form 안에 form 이 있다",
    "_csrf 없는 보내기",
    "글자도 이름표도 없는 단추",
    "alt 없는 그림",
    "<title> 이 비어 있다",
    "사람 눈에 영문 주소가 보인다",
])
def test_망친_곳을_짚어낸다(걸린것: str, 무엇: str) -> None:
    assert 무엇 in 걸린것


def test_멀쩡한_화면은_그냥_지나간다() -> None:
    멀쩡 = """<html><head><title>오늘 현황</title></head><body>
    <table><thead><tr><th rowspan="2">반</th><th colspan="2">출결</th></tr>
    <tr><th>결석</th><th>조퇴</th></tr></thead>
    <tbody><tr><td>지혜1</td><td>0</td><td>0</td></tr></tbody></table>
    <form method="post" action="/settings/kinder">
      <input type="hidden" name="_csrf" value="x"><button>저장</button></form>
    </body></html>"""
    assert A.살펴보기("시험", "/멀쩡한화면", 멀쩡, A.css_클래스()) == []


def test_태그_속_주소는_사람_눈에_보이는_것이_아니다() -> None:
    """상단바의 href="/attend" 를 보이는 글로 세면 안 된다 — 한 번 그랬다."""
    글 = A.보이는글('<a class="tab" href="/attend">출결 등록</a><script>var x="/board"</script>')
    assert "출결 등록" in 글
    assert "/attend" not in 글
    assert "/board" not in 글


def test_날짜를_따라_끝없이_돌지_않는다() -> None:
    """명단 화면에는 어제·내일 링크가 있다. 값까지 다르게 세면 멈추지 않는다."""
    assert A.모양("/board?d=2026-09-08") == A.모양("/board?d=2026-09-09")
    assert A.모양("/board?d=2026-09-08") != A.모양("/roster?d=2026-09-08")
