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


def test_화면_파일이_꾸러미에_담긴다():
    """templates 와 static 은 파이썬 파일이 아니라서 그냥 두면 설치본에 빠진다.

    소스에서 바로 돌릴 때는 멀쩡하다. 그래서 눈치채지 못한다. 그런데 pip install 로
    설치해서 돌리면(도커가 그렇다) 화면을 그리는 첫 순간에 죽는다.
    실제로 배포 준비 중에 만든 wheel 에 html·css·글꼴이 하나도 없었다.

    pyproject 의 package-data 가 꾸러미 안의 모든 비(非)파이썬 파일을 덮는지 본다.
    """
    import fnmatch
    from pathlib import Path

    import tomllib

    import firstout

    뿌리 = Path(firstout.__file__).resolve().parent
    conf = tomllib.loads((뿌리.parent.parent / "pyproject.toml").read_text(encoding="utf-8"))
    무늬 = conf["tool"]["setuptools"]["package-data"]["firstout"]

    빠진것 = []
    for f in 뿌리.rglob("*"):
        if not f.is_file() or f.suffix == ".py" or "__pycache__" in f.parts:
            continue
        안쪽 = f.relative_to(뿌리).as_posix()
        if not any(fnmatch.fnmatch(안쪽, 무늬하나) for 무늬하나 in 무늬):
            빠진것.append(안쪽)
    assert not 빠진것, f"꾸러미에 담기지 않는 파일: {빠진것}"


def test_배포에_필요한_값이_모두_안내되어_있다():
    """docker-compose 가 찾는 값은 .env.example 에 다 적혀 있어야 한다.

    빠뜨리면 NAS 에서 컨테이너가 뜨지 않고, 로그에는 낯선 변수 이름만 찍힌다.
    처음 올려보는 사람에게는 무슨 말인지 알 수 없는 오류가 된다.
    """
    import re
    from pathlib import Path

    뿌리 = Path(__file__).resolve().parent.parent
    compose = (뿌리 / "docker-compose.yml").read_text(encoding="utf-8")
    본보기 = (뿌리 / ".env.example").read_text(encoding="utf-8")

    쓰는값 = set(re.findall(r"\$\{([A-Z_][A-Z0-9_]*)", compose))
    적힌값 = set(re.findall(r"^([A-Z_][A-Z0-9_]*)=", 본보기, re.M))
    빠진값 = 쓰는값 - 적힌값
    assert not 빠진값, f".env.example 에 없는 값: {sorted(빠진값)}"


def test_NAS_에_올리는_스크립트가_빠뜨린_것을_챙긴다():
    """자료 폴더와 비밀 값은 빠뜨리면 컨테이너가 곧바로 죽는 자리다.

    문서에 적어두는 것만으로는 부족해서 스크립트가 대신 챙기게 했다.
    그 챙김이 사라지면 다시 같은 곳에서 막힌다.
    """
    from pathlib import Path

    sh = (Path(__file__).resolve().parent.parent / "deploy" / "nas-up.sh").read_text(
        encoding="utf-8")
    for 챙길것 in ("mkdir -p data",          # 없으면 주인이 root 가 된다
                  "MAJUNG_SECRET",           # 비어 있으면 서버가 안 뜬다
                  "docker-compose",          # 옛 DSM 도 받아준다
                  "/health"):                # 살아났는지 실제로 확인한다
        assert 챙길것 in sh, f"nas-up.sh 가 {챙길것} 을 챙기지 않는다"


def test_도커_이름은_영문만_쓴다():
    """컨테이너·이미지 이름에 한글을 쓰면 도커가 거절한다.

    실제로 `--name 시험` 이라고 지었다가 「exit code 125」만 남기고 끝났다.
    까닭이 로그에도 잘 안 보여서 한참 헤맸다. 도커가 받는 이름은
    [a-zA-Z0-9][a-zA-Z0-9_.-]* 뿐이다.
    """
    import re
    from pathlib import Path

    뿌리 = Path(__file__).resolve().parent.parent
    좋은이름 = re.compile(r"^[a-zA-Z0-9][a-zA-Z0-9_.-]*$")
    for f in list((뿌리 / ".github" / "workflows").glob("*.yml")) + [
        뿌리 / "docker-compose.yml"
    ]:
        글 = f.read_text(encoding="utf-8")
        이름들 = set(re.findall(r"--name\s+(\S+)", 글))
        이름들 |= set(re.findall(r"container_name:\s*(\S+)", 글))
        이름들 |= set(re.findall(r"^\s*image:\s*(\S+)", 글, re.M))
        나쁜 = sorted(n for n in 이름들 if not 좋은이름.match(n.split(":")[0]))
        assert not 나쁜, f"{f.name}: 도커가 거절할 이름 {나쁜}"


def test_자료_자리가_밖에_붙어_있다():
    """자료를 이미지 안에 넣으면 새 버전을 올릴 때마다 원아 자료가 날아간다.

    홈페이지는 다른 저장소(aurabus-site)로 갈라져 나갔다. 여기는 마중만 본다.
    """
    from pathlib import Path

    뿌리 = Path(__file__).resolve().parent.parent
    compose = (뿌리 / "docker-compose.yml").read_text(encoding="utf-8")

    assert "./data:/data" in compose, "자료 폴더가 안 붙어 있다"
    assert "nginx" not in compose, "홈페이지가 아직 이 저장소에 남아 있다"
    assert not (뿌리 / "site").exists(), "site/ 가 아직 남아 있다"


def test_빈_서명_키는_안_정한_것으로_본다():
    """MAJUNG_SECRET= 처럼 값을 비워두면 예전에는 검사를 그냥 통과했다.

    그 채로 서버가 서면 **빈 키로 세션에 서명**한다. 기본 키보다 나쁘다.
    Container Manager 에서 변수 이름만 넣고 값을 안 채우면 이렇게 온다.
    """
    import importlib
    import os

    from firstout import config

    본래 = os.environ.get("MAJUNG_SECRET")
    try:
        for 값, 막아야하나 in (("", True), ("   ", True), ("x" * 48, False)):
            os.environ["MAJUNG_SECRET"] = 값
            c = importlib.reload(config)
            assert c.IS_DEV_SECRET is 막아야하나, f"{값!r} 을 잘못 본다"
            if 막아야하나:
                assert c.SECRET_KEY == c.DEV_SECRET
    finally:
        if 본래 is None:
            os.environ.pop("MAJUNG_SECRET", None)
        else:
            os.environ["MAJUNG_SECRET"] = 본래
        importlib.reload(config)


def test_짧은_서명_키는_알려준다():
    import importlib
    import os

    from firstout import config

    본래 = os.environ.get("MAJUNG_SECRET")
    try:
        os.environ["MAJUNG_SECRET"] = "short"
        c = importlib.reload(config)
        assert c.SECRET_TOO_SHORT
        os.environ["MAJUNG_SECRET"] = "x" * c.MIN_SECRET
        c = importlib.reload(config)
        assert not c.SECRET_TOO_SHORT
    finally:
        if 본래 is None:
            os.environ.pop("MAJUNG_SECRET", None)
        else:
            os.environ["MAJUNG_SECRET"] = 본래
        importlib.reload(config)


def test_도커_안에서는_도커_이야기를_한다():
    """도커 안에서 「PowerShell 에서 $env:... 를 정하세요」는 아무 도움이 안 된다.

    실제로 NAS 에 올렸을 때 그 안내가 나와서 어디에 넣어야 하는지 알 수 없었다.
    """
    도커 = "\n".join(M.secret_help(True))
    내PC = "\n".join(M.secret_help(False))

    assert "Container Manager" in 도커
    assert "docker compose" in 도커
    assert "$env:" not in 도커, "도커 안에서 PowerShell 이야기를 한다"

    assert "$env:" in 내PC
    assert "Container Manager" not in 내PC


def test_배치_파일에는_한글이_없다():
    """chcp 로 코드페이지를 바꾼 뒤 cmd 는 파일의 나머지를 바이트 위치로 다시 읽는다.

    그래서 한글이 한 글자라도 있으면 — rem 주석 안이라도 — 그 뒤가 통째로 밀려
    cmd 가 깨진 글자를 명령으로 실행한다. 실제로 두 번 그렇게 깨졌다.
    한글 안내는 전부 파이썬·PowerShell 쪽에 둔다.
    """
    from pathlib import Path

    뿌리 = Path(__file__).resolve().parent.parent
    나쁜곳 = {}
    for f in 뿌리.glob("*.bat"):
        글 = f.read_text(encoding="utf-8")
        바깥글자 = sorted({c for c in 글 if ord(c) > 127})
        if 바깥글자:
            나쁜곳[f.name] = "".join(바깥글자)
    assert not 나쁜곳, f"배치 파일에 영문 아닌 글자가 있다: {나쁜곳}"


def _우리_ps1(뿌리):
    """우리가 쓴 PowerShell 파일만. 꾸러미가 딸려 넣은 것(.venv)은 뺀다."""
    남 = {".venv", ".git", "node_modules", "build"}
    return [f for f in 뿌리.rglob("*.ps1") if not (남 & set(f.parts))]


def test_PowerShell_파일은_BOM_으로_저장한다():
    """Windows PowerShell 5.1 은 BOM 이 없으면 .ps1 을 cp949 로 읽는다.

    그러면 한글이 깨지고, 깨진 글자가 코드로 읽혀 문법 오류가 난다. 실제로
    「Unexpected token '?=' in expression」 같은 알 수 없는 오류로 멈췄다.
    BOM 세 바이트가 있으면 UTF-8 로 읽는다.
    """
    from pathlib import Path

    뿌리 = Path(__file__).resolve().parent.parent
    BOM = b"\xef\xbb\xbf"
    없는것 = [f.name for f in _우리_ps1(뿌리) if not f.read_bytes().startswith(BOM)]
    assert not 없는것, f"BOM 없이 저장된 PowerShell 파일: {없는것}"


def test_PowerShell_이름은_영문으로_둔다():
    """BOM 이 사라져도 최소한 돌기는 해야 한다.

    한글은 화면에 보여줄 글에만 쓰고, 변수·함수 이름은 영문으로 둔다.
    그러면 BOM 을 잃어도 글자만 깨질 뿐 문법은 살아 있다.
    """
    import re
    from pathlib import Path

    뿌리 = Path(__file__).resolve().parent.parent
    나쁜곳 = {}
    for f in _우리_ps1(뿌리):
        글 = f.read_text(encoding="utf-8-sig")
        # 따옴표 안(사람에게 보여줄 글)은 뺀다
        코드 = re.sub(r'"[^"]*"|\'[^\']*\'', '""', 글)
        코드 = re.sub(r"^\s*#.*$", "", 코드, flags=re.M)
        이름 = set(re.findall(r"\$([^\W\d]\w*)", 코드))
        이름 |= set(re.findall(r"function\s+([^\W\d]\w*)", 코드))
        한글이름 = sorted(n for n in 이름 if any(ord(c) > 127 for c in n))
        if 한글이름:
            나쁜곳[f.name] = 한글이름
    assert not 나쁜곳, f"이름에 한글이 든 PowerShell 파일: {나쁜곳}"
