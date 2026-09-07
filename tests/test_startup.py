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
