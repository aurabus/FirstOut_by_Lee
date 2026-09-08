"""실행 시작 검증.

배너를 찍다가 죽으면 서버가 아예 뜨지 않는다. 실제로 한글 Windows 콘솔(cp949)에서
「—」 한 글자 때문에 시작에 실패한 적이 있어, 그 경로를 시험으로 묶어 둔다.
"""

from __future__ import annotations

import io

from firstout import main as M
from firstout.net import qr_svg


def test_배너가_cp949_콘솔에서도_죽지_않는다():
    """출력 인코딩이 cp949 여도 예외 없이 끝나야 한다."""
    buf = io.TextIOWrapper(io.BytesIO(), encoding="cp949", errors="replace")
    M._print_banner(8000, [], file=buf)   # 예외가 나면 이 줄에서 실패한다
    buf.flush()


def test_배너에_주소가_들어간다():
    buf = io.StringIO()
    M._print_banner(8123, [], file=buf)
    out = buf.getvalue()
    assert ":8123" in out
    assert "/connect" in out
    assert "127.0.0.1" in out


def test_유치원_이름이_배너에_보인다():
    class Fake:
        name = "가득유치원"
        status = "이용중"

    buf = io.StringIO()
    M._print_banner(8000, [Fake()], file=buf)
    assert "가득유치원" in buf.getvalue()


def test_qr_는_svg_를_돌려준다():
    svg = qr_svg("http://192.168.0.10:8000")
    assert svg.startswith("<svg")
    assert "</svg>" in svg
    assert "<rect" in svg


def test_utf8_콘솔_설정이_예외를_내지_않는다():
    M.use_utf8_console()


def test_안내문이_도착하는_화면은_모두_그것을_보여준다():
    """처리 결과 안내(flash)가 화면에 없으면 아무 일도 안 일어난 것처럼 보인다.

    실제로 「원아 95명을 등록했습니다」와 「비밀번호를 바꿨습니다」가 이렇게 묻혀 있었다.
    안내문을 보내는 곳이 늘어날 때마다 받는 쪽도 함께 챙기도록 시험으로 묶어 둔다.
    """
    from pathlib import Path

    import firstout

    # flash.put 이 보내는 곳들 (web/*.py 의 RedirectResponse 목적지)
    targets = [
        "board.html",      # "/"
        "roster.html",     # "/roster"
        "child.html",      # "/child/{id}"
        "list.html",       # "/list/{key}"
        "attend.html",     # "/attend"
        "users.html",      # "/users"
        "invite.html",     # "/users/{id}/invite"
        "join.html",       # "/join/{token}"
        "reauth.html",     # "/reauth"
        "upload.html",     # "/upload"
        "settings.html",   # "/settings"
        "operator.html",   # "/operator"
    ]
    root = Path(firstout.__file__).parent / "templates"
    missing = [
        name for name in targets
        if "{% if msg %}" not in (root / name).read_text(encoding="utf-8")
    ]
    assert missing == [], f"안내문을 보여주지 않는 화면: {missing}"


def test_사용_안내가_바깥_자원을_쓰지_않는다():
    """인터넷이 끊겨도 열려야 한다 — 글꼴도 그림도 서버 안에 있다.

    안내를 밖에서 끌어오게 만들면, 정작 필요한 순간(연결이 이상할 때)에 안 열린다.
    """
    from pathlib import Path

    import firstout

    html = (Path(firstout.__file__).parent / "templates" / "help.html").read_text(
        encoding="utf-8"
    )
    for outside in ("fonts.googleapis", "cdnjs", "jsdelivr", "http://", "https://"):
        assert outside not in html, outside


def test_사용_안내의_모든_대목에_갈_수_있다():
    """화면에서 「? 도움말」을 눌렀을 때 없는 자리로 보내면 안 된다."""
    import re
    from pathlib import Path

    import firstout

    root = Path(firstout.__file__).parent / "templates"
    help_html = (root / "help.html").read_text(encoding="utf-8")
    have = set(re.findall(r'<section class="hp" id="([^"]+)">', help_html))
    assert len(have) >= 10

    wanted = set()
    for f in root.glob("*.html"):
        wanted |= set(re.findall(r'href="/help#([^"]+)"', f.read_text(encoding="utf-8")))
    assert wanted, "화면에서 안내로 가는 길이 하나도 없다"
    assert wanted <= have, f"없는 대목으로 보낸다: {wanted - have}"


def test_화면이_쓰는_모든_class_가_CSS_에_있다():
    """공통 결(aurabus.css)과 이 프로그램 조각(app.css)을 함께 본다.

    실제로 출결 화면의 CSS 가 통째로 빠져 있어 화면이 깨진 적이 있다.
    """
    import re
    from pathlib import Path

    import firstout

    static = Path(firstout.__file__).parent / "static"
    css = " ".join(
        re.sub(r"/\*.*?\*/", "", (static / n).read_text(encoding="utf-8"), flags=re.S)
        for n in ("aurabus.css", "app.css")
    )
    defined = set(re.findall(r"\.([A-Za-z][\w-]*)", css))

    used = set()
    for f in (Path(firstout.__file__).parent / "templates").glob("*.html"):
        for m in re.findall(r'class="([^"]*)"', f.read_text(encoding="utf-8")):
            m = re.sub(r"\{\{.*?\}\}|\{%.*?%\}", " ", m)
            used |= {n for n in m.split() if n and n[0].isascii() and n[0].isalpha()}

    assert used <= defined, f"CSS 에 없는 class: {sorted(used - defined)}"


def test_CSS_중괄호가_맞는다():
    """닫는 중괄호 하나가 모자라면 그 뒤 규칙이 통째로 먹히지 않는다.

    CSS 를 두 파일로 나누다가 여러 줄짜리 규칙을 첫 줄에서 잘라, 닫는 중괄호 여섯 개가
    사라진 적이 있다. 화면이 통째로 깨졌는데 아무 오류도 나지 않았다 —
    브라우저는 잘못된 CSS 를 조용히 건너뛰기 때문이다.
    """
    import re
    from pathlib import Path

    import firstout

    static = Path(firstout.__file__).parent / "static"
    for name in ("aurabus.css", "app.css"):
        text = re.sub(r"/\*.*?\*/", "", (static / name).read_text(encoding="utf-8"),
                      flags=re.S)
        opened, closed = text.count("{"), text.count("}")
        assert opened == closed, f"{name}: 여는 {opened} · 닫는 {closed}"


def test_화면용_규칙이_인쇄_안에_갇히지_않는다():
    """@media print 안에만 있는 규칙은 화면에서 아무 일도 하지 않는다."""
    import re
    from pathlib import Path

    import firstout

    static = Path(firstout.__file__).parent / "static"
    css = " ".join((static / n).read_text(encoding="utf-8")
                   for n in ("aurabus.css", "app.css"))
    outside = re.sub(r"@media print\{(?:[^{}]|\{[^{}]*\})*\}", "", css, flags=re.S)
    for sel in (".gl", ".gl-item", ".att", ".att-item", ".board", ".tiles", ".btn"):
        assert re.search(re.escape(sel) + r"\{", outside), f"{sel} 이 인쇄 안에만 있다"


def test_표의_칸_수가_줄마다_같다():
    """머리글이 몸통보다 한 칸 많으면 표가 통째로 어긋난다.

    실제로 「귀가 현황」에 colspan=3 을 걸어 놓고 아래에는 칸을 둘만 두어,
    빈 유령 칸이 하나 생기고 머리글이 값과 한 칸씩 밀린 적이 있다.
    브라우저는 아무 말도 하지 않고 그냥 그렇게 그린다.
    """
    import re
    from pathlib import Path

    import firstout

    def 줄별_칸수(표: str) -> list[int]:
        내려오는: dict[int, int] = {}          # rowspan 으로 아랫줄까지 먹는 칸
        너비 = []
        for i, 줄 in enumerate(re.findall(r"<tr\b[^>]*>(.*?)</tr>", 표, re.S)):
            w = 내려오는.pop(i, 0)
            for 칸 in re.findall(r"<(?:th|td)\b([^>]*)>", 줄):
                cs = int((re.search(r'colspan="(\d+)"', 칸) or [0, 1])[1])
                rs = int((re.search(r'rowspan="(\d+)"', 칸) or [0, 1])[1])
                w += cs
                for k in range(1, rs):
                    내려오는[i + k] = 내려오는.get(i + k, 0) + cs
            너비.append(w)
        return 너비

    for f in sorted((Path(firstout.__file__).parent / "templates").glob("*.html")):
        본문 = re.sub(r"\{\{.*?\}\}|\{%.*?%\}", "", f.read_text(encoding="utf-8"), flags=re.S)
        for 표 in re.findall(r"<table\b.*?</table>", 본문, re.S):
            너비 = 줄별_칸수(표)
            assert len(set(너비)) <= 1, f"{f.name}: 줄마다 칸 수가 다르다 {너비}"


def test_CSS_가_없는_값을_쓰지_않는다():
    """var(--없는것) 이 들어가면 그 줄만 조용히 버려진다.

    실제로 --pine-line 을 정의하지 않은 채 쓰고 있었다. 테두리 색이 그냥 안 먹었는데
    오류는 어디에도 나지 않았다. 모서리·색 같은 값은 전부 결(토큰)에서 가져다 쓰므로
    이름 하나가 어긋나면 그 자리만 딴 모습이 된다.
    """
    import re
    from pathlib import Path

    import firstout

    static = Path(firstout.__file__).parent / "static"
    css = " ".join(
        re.sub(r"/\*.*?\*/", "", (static / n).read_text(encoding="utf-8"), flags=re.S)
        for n in ("aurabus.css", "app.css"))
    정의 = set(re.findall(r"(--[\w-]+)\s*:", css))
    쓴것 = set(re.findall(r"var\((--[\w-]+)", css))
    assert not (쓴것 - 정의), f"정의 없이 쓰는 값: {sorted(쓴것 - 정의)}"


def test_모서리는_결에서_가져다_쓴다():
    """모서리를 화면마다 직접 적으면 어떤 곳은 둥글고 어떤 곳은 각지게 남는다.

    부드러운 인상을 결(--r/--r-sm/--r-xs/--r-pill)로 한곳에서 정하기로 했으므로,
    프로그램 CSS 에는 px 로 적은 모서리가 없어야 한다. 원(50%)과 인쇄용 0 은 뺀다.
    """
    import re
    from pathlib import Path

    import firstout

    app = (Path(firstout.__file__).parent / "static" / "app.css").read_text(encoding="utf-8")
    직접 = [v for v in re.findall(r"border-radius:([^;}]*)", app)
            if "var(" not in v and v.strip() not in ("0", "50%")]
    assert not 직접, f"결을 쓰지 않고 직접 적은 모서리: {직접}"
