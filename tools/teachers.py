"""동료 선생님을 QR 로 들이고, 그분들이 정말 쓸 수 있는가.

총괄 관리자가 계정을 만들면 **QR 하나**가 뜬다. 선생님은 그것을 자기 휴대폰으로
찍어 비밀번호를 정하고 그 자리에서 들어온다. 카카오톡으로 비밀번호가 오가지
않게 하려고 그렇게 만들었다.

그 길이 한 군데라도 막히면 개원 첫날 선생님 대여섯 분이 문 앞에 서 있게 된다.
그래서 처음부터 끝까지 사람과 똑같이 걸어 본다.

    python tools/teachers.py

여기서 가장 조심스러운 것은 **QR 안에 든 주소**다. 그림은 멀쩡히 떠도 그 안에
`127.0.0.1` 이 들어 있으면 선생님 휴대폰에서는 아무것도 안 열린다. 눈으로는
절대 못 잡는다. 그래서 화면에 그려진 그림에서 점을 도로 읽어, 우리가 기대하는
주소로 만든 그림과 **한 점 한 점 맞춰 본다.**

임시 자료 폴더를 쓰고 끝나면 지운다. 쓰던 자료와 NAS 는 건드리지 않는다.
"""

from __future__ import annotations

import http.cookiejar
import os
import random
import re
import shutil
import socket
import string
import subprocess
import sys
import tempfile
import time
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

뿌리 = Path(__file__).resolve().parent.parent
좋음, 나쁨 = "  ○", "  ✗"

유치원 = "주덕화곡초등학교 병설유치원"
원장 = ("지민희", "jimin", "1234")
원장새비번 = "majung-jimin-2026"
바깥주소 = "https://majung.aurabus.com"      # 실제 서비스와 같은 값으로 띄운다

# (이름, 아이디, 직함, 맡을 반, 정할 비밀번호)
선생님들 = [
    ("김하늘", "hanul", "담임", "지혜1", "hanul-2026-majung"),
    ("이바다", "bada", "담임", "지혜2", "bada-2026-majung"),
    ("박나무", "namu", "돌봄", "", "namu-2026-majung"),
]
아이들 = [("이서준", "박영희", "모"), ("정하윤", "정미경", "모"), ("오시우", "오준호", "부")]


class 걸림(Exception):
    """더 갈 수 없을 때."""


class 프록시뒤(http.cookiejar.DefaultCookiePolicy):
    """우리는 https 프록시 뒤에 있는 브라우저인 척한다.

    실제 서버는 DSM 역방향 프록시 뒤에서 https 로 서비스된다. 그 설정 그대로
    띄워야 **진짜 쓰는 것과 같은 길**을 걷는데, 그러면 서버가 Secure 쿠키를
    내준다. 우리는 여기서 http 로 말을 걸므로 파이썬이 그 쿠키를 도로 안 보낸다.
    브라우저 쪽 사정일 뿐이니 여기서만 그 규칙을 풀어 준다.
    """

    def return_ok_secure(self, cookie, request) -> bool:   # noqa: ARG002
        return True


class 손님:
    """브라우저 한 개."""

    def __init__(self, 바탕: str) -> None:
        self.바탕 = 바탕.rstrip("/")
        self.항아리 = http.cookiejar.CookieJar(프록시뒤())
        self.문 = urllib.request.build_opener(
            urllib.request.HTTPCookieProcessor(self.항아리))
        self.보기("/signin")     # CSRF 쪽지를 먼저 받아 둔다 — 사람도 화면을 먼저 연다

    def 보기(self, 길: str) -> tuple[int, str, str]:
        try:
            req = urllib.request.Request(self.바탕 + 길)
            req.add_header("X-Forwarded-Proto", "https")   # 프록시가 붙이는 그 헤더
            r = self.문.open(req, timeout=15)
            return r.status, r.url, r.read().decode("utf-8", "replace")
        except urllib.error.HTTPError as e:
            return e.code, 길, e.read().decode("utf-8", "replace")
        except OSError as e:
            return 0, 길, str(e)

    def 보내기(self, 길: str, 값: dict[str, str]) -> tuple[int, str, str]:
        값 = dict(값)
        값.setdefault("_csrf", self.토큰())
        몸 = urllib.parse.urlencode(값, encoding="utf-8").encode()
        req = urllib.request.Request(self.바탕 + 길, data=몸)
        req.add_header("Content-Type", "application/x-www-form-urlencoded")
        req.add_header("Referer", self.바탕 + "/")
        req.add_header("X-Forwarded-Proto", "https")
        try:
            r = self.문.open(req, timeout=15)
            return r.status, r.url, r.read().decode("utf-8", "replace")
        except urllib.error.HTTPError as e:
            return e.code, 길, e.read().decode("utf-8", "replace")
        except OSError as e:
            return 0, 길, str(e)

    def 토큰(self) -> str:
        for c in self.항아리:
            if "csrf" in c.name.lower():
                return c.value
        return ""

    def 어디(self) -> str:
        _, 주소, _ = self.보기("/")
        return urllib.parse.urlparse(주소).path

    def 들어가기(self, 길: str, 비번: str) -> tuple[int, str]:
        """비밀번호를 한 번 더 묻는 벽이 있으면 대답하고 다시 연다."""
        코드, 주소, h = self.보기(길)
        if urllib.parse.urlparse(주소).path == "/reauth":
            self.보내기("/reauth", {"password": 비번, "next": 길})
            코드, _, h = self.보기(길)
        return 코드, h


def 글만(h: str) -> str:
    h = re.sub(r"(?is)<(script|style|svg)[^>]*>.*?</\1>", " ", h)
    return re.sub(r"\s+", " ", re.sub(r"(?s)<[^>]+>", " ", h)).strip()


# ── QR 안을 들여다본다 ──────────────────────────────────────

def qr_점읽기(svg: str) -> set[tuple[int, int]] | None:
    """화면에 그려진 QR 그림에서 **검은 점의 자리**를 도로 읽는다.

    net.qr_svg 는 이어진 칸을 하나의 <rect> 로 묶어 그린다. 그래서 너비를 보고
    칸 수로 되돌려야 한다. 눈으로는 그림이 멀쩡한지만 알 수 있고, 그 안에 무슨
    주소가 들었는지는 알 수 없다 — 그것이 이 함수가 있는 까닭이다.
    """
    if "<svg" not in svg:
        return None
    네모 = [tuple(int(v) for v in m.groups()) for m in re.finditer(
        r'<rect x="(\d+)" y="(\d+)" width="(\d+)" height="(\d+)"', svg)]
    if not 네모:
        return None
    # 한 칸의 크기는 따로 적혀 있지 않다. 다만 모든 네모의 **높이가 곧 한 칸**이라
    # (가로로만 이어 붙여 그리므로) 그 값을 그대로 쓴다. 숫자를 손으로 적어 두면
    # 그리는 쪽이 바뀌는 날 이 검사기가 조용히 거짓말을 한다.
    상자 = min(h for _x, _y, _w, h in 네모)
    점 = set()
    for x, y, w, _h in 네모:
        for i in range(w // 상자):
            점.add((x // 상자 + i, y // 상자))
    return 점


def qr_기대값(글: str, quiet: int = 2) -> set[tuple[int, int]]:
    """이 주소라면 QR 이 이렇게 생겨야 한다 — 견줄 대상."""
    import qrcode

    qr = qrcode.QRCode(border=quiet, box_size=1)
    qr.add_data(글)
    qr.make(fit=True)
    return {(x, y) for y, 줄 in enumerate(qr.get_matrix())
            for x, 켜짐 in enumerate(줄) if 켜짐}


# ── 서버 ────────────────────────────────────────────────────

def 빈포트() -> int:
    for 후보 in (8771, 8772, 8773):
        try:
            with socket.socket() as s:
                s.bind(("127.0.0.1", 후보))
                return 후보
        except OSError:
            continue
    with socket.socket() as s:
        s.bind(("127.0.0.1", 0))
        return int(s.getsockname()[1])


def 서버_띄우기(자료: Path) -> tuple[subprocess.Popen, str]:
    포트 = 빈포트()
    환경 = {**os.environ, "MAJUNG_DATA": str(자료),
            "MAJUNG_SECRET": "".join(random.choices(string.ascii_letters + string.digits, k=64)),
            # 실제 서버와 같은 값을 준다 — QR 에 무엇이 들어가는지는 이 값이 정한다
            "MAJUNG_PUBLIC_URL": 바깥주소,
            "MAJUNG_PROXY_HOPS": "1",
            "PYTHONUTF8": "1", "PYTHONIOENCODING": "utf-8",
            "PYTHONPATH": str(뿌리 / "src")}
    이름, 아이디, 비번 = 원장
    난 = subprocess.run(
        [sys.executable, "-m", "firstout.main", "--setup-only",
         "--open-kinder", 유치원, "--admin", f"{이름}:{아이디}:{비번}"],
        cwd=str(뿌리), env=환경, capture_output=True, text=True,
        encoding="utf-8", errors="replace")
    if 난.returncode != 0:
        raise 걸림("유치원을 열지 못했습니다:\n" + 난.stdout + 난.stderr)

    서버 = subprocess.Popen(
        [sys.executable, "-m", "uvicorn", "firstout.main:app",
         "--host", "127.0.0.1", "--port", str(포트), "--log-level", "warning"],
        cwd=str(뿌리), env=환경, stdout=subprocess.DEVNULL,
        stderr=subprocess.STDOUT)
    바탕 = "http://127.0.0.1:" + str(포트)
    for _ in range(60):
        if 서버.poll() is not None:
            raise 걸림("서버가 곧바로 죽었습니다")
        try:
            urllib.request.urlopen(바탕 + "/health", timeout=2)
            return 서버, 바탕
        except OSError:
            time.sleep(0.5)
    서버.kill()
    raise 걸림("서버가 일어나지 않았습니다")


# ── 걸어 본다 ───────────────────────────────────────────────

def 걷기(바탕: str, 자료: Path, 말: list[str]) -> None:
    def 확인(맞나: bool, 무엇: str, 왜: str = "") -> None:
        if 맞나:
            print(좋음 + " " + 무엇)
        else:
            print(나쁨 + " " + 무엇 + ("  — " + 왜 if 왜 else ""))
            말.append(무엇 + ("  — " + 왜 if 왜 else ""))

    선생님이름, 선생님아이디, _직함, _반, _비번 = 선생님들[0]

    # ── 1. 총괄 관리자가 들어온다 ─────────────────────────
    print("\n── 1. 지민희 선생님이 들어옵니다 ─────────")
    지민희 = 손님(바탕)
    _, 아이디, 첫비번 = 원장
    지민희.보내기("/signin", {"login_id": 아이디, "password": 첫비번, "device": "shared"})
    확인(지민희.어디() == "/me/password", "첫 비밀번호를 정하라고 붙잡는다")
    지민희.보내기("/me/password",
                {"current": 첫비번, "password": 원장새비번, "password2": 원장새비번})
    확인(지민희.어디() != "/me/password", "새 비밀번호를 정하면 풀려난다")

    # 반 번호를 미리 챙겨 둔다
    _, h = 지민희.들어가기("/settings", 원장새비번)
    반번호: dict[str, str] = {}
    _, _, rh = 지민희.보기("/roster")
    for 값, 이름 in re.findall(r'<option value="(\d+)"[^>]*>\s*([^<\s]+)', rh):
        반번호.setdefault(이름, 값)
    확인(len(반번호) >= 3, f"반 {len(반번호)}개를 고를 수 있다")

    # ── 2. 동료 선생님을 더하고 QR 을 띄운다 ──────────────
    print("\n── 2. 동료 선생님을 더합니다 ─────────────")
    # 계정 화면은 비밀번호를 한 번 더 묻는다. 그 벽을 넘기 전에 보낸 것은
    # 조용히 버려진다 — 그것도 모르고 「왜 한 분만 안 생기지」 하고 헤맸다.
    지민희.들어가기("/users", 원장새비번)

    초대 = {}
    for 이름, 로그인, 직함, 반, _ in 선생님들:
        # 「추가」를 누르면 **그 자리에서 초대 화면으로 넘어간다.** 초대 원문은
        # 그 한 번의 응답에만 실려 온다 (쿠키로 왔다가 곧바로 지워진다).
        # 다시 열면 이미 없다 — 화면에 오래 떠 있지 않게 하려고 그렇게 만들었다.
        _코드, 주소, ih = 지민희.보내기("/users/add", {
            "name": 이름, "login_id": 로그인, "title": 직함,
            "class_id": 반번호.get(반, ""), "role": "선생님"})
        번호 = re.search(r"/users/(\d+)/invite", 주소)
        만든이 = 번호.group(1) if 번호 else ""
        찾 = re.search(r"/join/([A-Za-z0-9_\-]+)", ih)
        초대[이름] = (만든이, 찾.group(1) if 찾 else "", ih)
        확인(bool(만든이) and bool(찾),
             f"{이름} 선생님을 만들면 곧바로 초대가 뜬다", f"넘어간 곳 {주소}")

    _, uh = 지민희.들어가기("/users", 원장새비번)
    보임 = [이름 for 이름, *_ in 선생님들 if 이름 in uh]
    확인(len(보임) == len(선생님들), f"선생님 {len(선생님들)}분이 목록에 보인다", str(보임))
    확인("담임" in uh and "돌봄" in uh, "직함이 그대로 적힌다")

    # ── 3. QR 안에 무엇이 들어 있나 ───────────────────────
    print("\n── 3. QR 을 들여다봅니다 ─────────────────")
    _만든이, 토큰, ih = 초대[선생님이름]
    확인("<svg" in ih, "QR 그림이 화면에 그려진다")

    기대주소 = f"{바깥주소}/join/{토큰}"
    확인(기대주소 in ih, "화면에 적힌 주소가 바깥 주소다",
         "127.0.0.1 이 적혀 있으면 휴대폰에서 안 열립니다")

    # 원문은 그 한 번만 보여주고 사라져야 한다 — 화면에 오래 떠 있으면
    # 지나가던 사람이 찍어 갈 수 있다
    _, _, 다시 = 지민희.보기(f"/users/{_만든이}/invite")
    확인("<svg" not in 다시, "새로고침하면 QR 이 사라진다")
    확인("다시" in 글만(다시) or "새로" in 글만(다시),
         "사라진 자리에 다시 만드는 길을 알려준다", 글만(다시)[:70])

    점 = qr_점읽기(ih)
    확인(bool(점), "QR 그림에서 점을 읽어낼 수 있다")
    if 점:
        맞나 = 점 == qr_기대값(기대주소)
        확인(맞나, "QR 이 **정말 그 주소**를 담고 있다",
             "그림은 떴지만 안에 든 주소가 다릅니다")
        확인("127.0.0.1" not in ih and "localhost" not in ih,
             "QR 화면 어디에도 내부 주소가 없다")

    # ── 4. 선생님이 QR 을 찍고 들어온다 ───────────────────
    print("\n── 4. 선생님들이 QR 로 들어옵니다 ────────")
    브라우저: dict[str, 손님] = {}
    for 이름, 로그인, _직함, _반, 새비번 in 선생님들:
        _, 토큰, _ = 초대[이름]
        샘 = 손님(바탕)
        코드, _, jh = 샘.보기(f"/join/{토큰}")
        확인(코드 == 200 and 이름 in jh, f"{이름} 선생님 — 초대 화면이 열린다", str(코드))
        샘.보내기(f"/join/{토큰}",
                {"password": 새비번, "password2": 새비번, "device": "personal"})
        확인(샘.어디() not in ("/signin", f"/join/{토큰}"),
             f"{이름} 선생님 — 비밀번호를 정하고 그 자리에서 들어온다", 샘.어디())
        브라우저[이름] = 샘

    # ── 4-2. 다음 날 다시 들어온다 ────────────────────────
    # QR 은 그날 한 번뿐이다. 그 다음부터는 아이디와 본인이 정한 비밀번호로
    # 들어오셔야 한다. 여기가 막히면 이튿날 아침에 아무도 못 들어온다.
    print("\n── 4-2. 이튿날 아이디로 다시 들어옵니다 ──")
    for 이름, 로그인, _직함, _반, 새비번 in 선생님들:
        샘 = 브라우저[이름]
        샘.보내기("/signout", {})
        확인(샘.어디() == "/signin", f"{이름} 선생님 — 로그아웃된다")

        내일 = 손님(바탕)      # 다음 날 아침, 쿠키가 없는 상태
        내일.보내기("/signin", {"login_id": 로그인, "password": 새비번,
                             "device": "personal"})
        자리 = 내일.어디()
        확인(자리 not in ("/signin", "/me/password"),
             f"{이름} 선생님 — 아이디와 본인 비밀번호로 들어온다", 자리)
        내일.보내기("/signin", {"login_id": 로그인, "password": "아무거나틀린값"})
        브라우저[이름] = 내일

    샘 = 브라우저[선생님이름]
    _, _, bh = 샘.보기("/board")
    확인(선생님이름 in bh, "화면 위에 본인 이름이 보인다")

    # ── 5. 초대는 한 번만 ─────────────────────────────────
    print("\n── 5. 초대가 한 번만 되는가 ──────────────")
    _, 토큰, _ = 초대[선생님이름]
    남 = 손님(바탕)
    _, _, jh = 남.보기(f"/join/{토큰}")
    확인("지났" in 글만(jh) or "끝난" in 글만(jh) or "다시" in 글만(jh),
         "이미 쓴 초대는 다시 안 열린다", 글만(jh)[:70])
    남.보내기(f"/join/{토큰}", {"password": "namuel-cheoeum", "password2": "namuel-cheoeum"})
    확인(남.어디() == "/signin", "쓴 초대로는 비밀번호도 못 정한다", 남.어디())

    # 기한이 지난 것도 죽는가 — 시계를 돌릴 수 없으니 기한을 과거로 옮겨 본다
    이름2 = 선생님들[1][0]
    만든이2, _, _ = 초대[이름2]
    _, _, ih2 = 지민희.보내기(f"/users/{만든이2}/invite", {})
    찾2 = re.search(r"/join/([A-Za-z0-9_\-]+)", ih2)
    if 찾2:
        낡히기(자료, 찾2.group(1))
        늦은이 = 손님(바탕)
        _, _, jh2 = 늦은이.보기(f"/join/{찾2.group(1)}")
        확인("지났" in 글만(jh2) or "끝난" in 글만(jh2) or "다시" in 글만(jh2),
             "10분이 지난 초대도 죽는다", 글만(jh2)[:70])

    # ── 6. 선생님이 실제로 쓸 수 있는가 ───────────────────
    print("\n── 6. 선생님이 쓸 수 있는가 ──────────────")
    샘 = 브라우저[선생님이름]
    for 무엇, 길 in (("오늘 현황", "/board"), ("출결 등록", "/attend"),
                    ("원아 명부", "/roster"), ("사용 안내", "/help"),
                    ("접속 안내", "/connect")):
        코드, 주소, _ = 샘.보기(길)
        확인(코드 == 200 and urllib.parse.urlparse(주소).path == 길,
             f"{무엇} 을 본다", f"{코드} · {주소}")

    for 무엇, 길 in (("선생님 관리", "/users"), ("설정", "/settings")):
        _, 주소, _ = 샘.보기(길)
        확인(urllib.parse.urlparse(주소).path != 길,
             f"{무엇} 에는 못 들어간다", "들어가집니다")

    # ── 7. 원장이 아이를 올리고, 선생님이 귀가시킨다 ──────
    print("\n── 7. 아이를 올리고 선생님이 귀가시킵니다 ─")
    반 = 반번호.get(선생님들[0][3], next(iter(반번호.values()), ""))
    for 아이, 보호자, 사이 in 아이들:
        지민희.보내기("/roster/add", {"name": 아이, "class_id": 반,
                                   "g_name": 보호자, "g_relation": 사이,
                                   "g_phone": "010-0000-0000"})
    _, _, rh = 지민희.보기("/roster")
    확인(all(아이 in rh for 아이, *_ in 아이들), "아이 3명이 명부에 오른다")

    아이번호 = re.findall(r'/child/(\d+)"', rh)
    첫아이 = 아이번호[0] if 아이번호 else ""
    _, _, ch = 지민희.보기(f"/child/{첫아이}")
    차수 = re.findall(r'value="r:(\d+)"', ch)
    import datetime as dt
    오늘 = dt.date.today()
    보는날 = 오늘 + dt.timedelta(days=(7 - 오늘.weekday()) % 7) if 오늘.weekday() >= 5 else 오늘
    날 = 보는날.isoformat()
    if 차수:
        for 요일 in range(5):
            지민희.보내기(f"/child/{첫아이}/plan", {"weekday": str(요일), "how": "r:" + 차수[0]})

    # 선생님이 출결을 찍는다
    코드, _, ah = 샘.보기(f"/attend?d={날}")
    확인(코드 == 200 and 아이들[0][0] in ah, "선생님 출결 화면에 우리 반 아이가 보인다")

    찾은키, 찾은h = "", ""
    for 키 in ("i1", "b1", "b2", "i2", "care"):
        코드, _, lh = 샘.보기(f"/list/{키}?d={날}")
        if 코드 == 200 and 아이들[0][0] in lh:
            찾은키, 찾은h = 키, lh
            break
    확인(bool(찾은키), "선생님이 그날 귀가 명단을 본다")

    if 찾은키:
        길 = f"/list/{찾은키}/{첫아이}"
        전 = 찾은h.count("/undo")
        if "signature" in 찾은h:
            샘.보내기(길 + "/sign", {"receiver": "default", "receiver_name": 아이들[0][1],
                                  "receiver_rel": 아이들[0][2],
                                  "signature": "data:image/png;base64,iVBORw0KGgo=",
                                  "memo": "", "d": 날})
        else:
            샘.보내기(길 + "/check", {"how": "", "d": 날})
        _, _, lh = 샘.보기(f"/list/{찾은키}?d={날}")
        확인(lh.count("/undo") > 전, "선생님이 귀가 처리를 한다")

        _, _, bh = 지민희.보기(f"/board?d={날}")
        띠 = re.search(r'title="귀가 (\d+) · 현원 (\d+)', bh)
        확인(bool(띠) and 띠.group(1) == "1",
             "원장 화면에 그 처리가 바로 보인다", 띠.group(0) if 띠 else "못 찾음")

    # ── 8. 기록에 남는가 ──────────────────────────────────
    print("\n── 8. 누가 했는지 남는가 ─────────────────")
    _, ah2 = 지민희.들어가기("/audit", 원장새비번)
    확인(선생님이름 in ah2, f"{선생님이름} 선생님이 한 일이 기록에 남는다")


def 낡히기(자료: Path, 토큰: str) -> None:
    """그 초대의 기한을 과거로 옮긴다 — 10분을 기다리지 않으려고."""
    import hashlib
    import sqlite3

    표식 = hashlib.sha256(토큰.encode()).hexdigest()
    c = sqlite3.connect(자료 / "majung.db")
    c.execute("update invite set expires_at = datetime('now','-1 hour') where token_hash = ?",
              (표식,))
    c.commit()
    c.close()


def main() -> int:
    자료 = Path(tempfile.mkdtemp(prefix="majung-teachers-"))
    말: list[str] = []
    서버 = None
    print()
    print("  선생님을 QR 로 들이는 길을 처음부터 끝까지 걸어 봅니다")
    print("  임시 자리: " + str(자료))
    try:
        서버, 바탕 = 서버_띄우기(자료)
        print("  서버: " + 바탕 + "  (바깥 주소는 " + 바깥주소 + " 로 둡니다)")
        걷기(바탕, 자료, 말)
    except 걸림 as e:
        print("\n" + 나쁨 + " " + str(e))
        말.append(str(e))
    finally:
        if 서버 is not None:
            서버.terminate()
            try:
                서버.wait(timeout=10)
            except subprocess.TimeoutExpired:
                서버.kill()
        for _ in range(10):
            shutil.rmtree(자료, ignore_errors=True)
            if not 자료.exists():
                break
            time.sleep(0.5)
        print("\n  임시 자료: " + ("아직 남아 있습니다" if 자료.exists() else "지웠습니다"))

    print()
    if 말:
        print("  걸린 것 " + str(len(말)) + "개")
        for m in 말:
            print("    - " + m)
        print()
        return 1
    print("  선생님을 들이는 길이 처음부터 끝까지 지나갑니다.")
    print()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
