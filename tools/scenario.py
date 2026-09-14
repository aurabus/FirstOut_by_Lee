"""선생님을 더하고, 아이를 올리고, 귀가를 체크한다 — 처음부터 끝까지 한 번.

여기까지 있는 시험 209개는 모두 **안쪽 로직**을 본다. 화면을 눌러 넘어가는
길 자체 — 로그인하고, 폼을 채워 보내고, 다음 화면으로 넘어가는 그 길 —
은 아무도 안 보고 있었다. 사람이 실제로 하는 일이 바로 그 길이다.

이 도구는 **손님과 똑같은 방법**으로 그 길을 한 번 걸어 본다.
서버를 직접 띄우고, 임시 자료 폴더를 쓰고, 끝나면 지운다.
지금 쓰는 자료에는 손대지 않는다.

    python tools/scenario.py            자동으로 한 바퀴 걷고 끝낸다
    python tools/scenario.py --손으로    자리만 깔고 기다린다 (내가 직접 눌러본다)

**어느 쪽이든 임시 자료 폴더를 쓰고, 끝나면 지웁니다.** 지금 쓰는 자료와
NAS 의 자료에는 손대지 않습니다. 시범 운영 자료에 연습 흔적을 남기지 않으려면
연습은 여기서 하는 편이 낫다 — 서버에서는 감사 로그와 백업에 그대로 남는다.

걷는 길:
    0. 로그인 전에 사용 안내를 볼 수 있는지
    1. 유치원을 연다 (시범 운영과 똑같이 --open-kinder 로)
    2. 총괄 관리자로 들어간다 — 첫 비밀번호를 정하라고 막는지
    3. 반을 하나 더 만든다
    4. 선생님을 더하고 초대를 만든다
    5. 아이 셋을 올린다 (보호자까지)
    6. 주간 귀가 계획을 정한다
    7. 오늘 명단에 그 아이들이 나오는지
    8. 귀가를 체크한다
    9. 반별 현황에 반영되는지
   10. 선생님이 초대로 들어와 같은 명단을 보는지
   11. 감사 로그에 남았는지
"""

from __future__ import annotations

import datetime as dt
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

유치원 = "주덕화곡초등학교병설유치원"
관리자 = ("지민희", "admin", "1234")
새비번 = "majung-2026-pilot"
선생님 = ("김하늘", "hanul")
아이들 = [
    ("이서준", "박영희", "모", "010-2345-6789"),
    ("정하윤", "정미경", "모", "010-3456-7890"),
    ("오시우", "오준호", "부", "010-4567-8901"),
]


class 걸림(Exception):
    """시나리오가 더 갈 수 없을 때."""


# ── 손님 한 사람 ────────────────────────────────────────────

class 손님:
    """브라우저 한 개. 쿠키를 들고 다니고 폼을 채워 보낸다."""

    def __init__(self, 바탕: str) -> None:
        self.바탕 = 바탕.rstrip("/")
        self.항아리 = http.cookiejar.CookieJar()
        self.문 = urllib.request.build_opener(
            urllib.request.HTTPCookieProcessor(self.항아리))

    def 보기(self, 길: str) -> tuple[int, str, str]:
        try:
            r = self.문.open(self.바탕 + 길, timeout=15)
            return r.status, r.url, r.read().decode("utf-8", "replace")
        except urllib.error.HTTPError as e:
            return e.code, 길, e.read().decode("utf-8", "replace")
        except OSError as e:
            return 0, 길, str(e)

    def 보내기(self, 길: str, 값: dict[str, str]) -> tuple[int, str, str]:
        """폼 하나를 채워 보낸다. _csrf 는 쿠키에서 주워 넣는다.

        토큰을 손으로 지어내면 CSRF 방어가 있는지조차 확인이 안 된다.
        사람이 하는 것과 같게, 브라우저가 들고 있는 값을 그대로 쓴다.
        """
        값 = dict(값)
        값.setdefault("_csrf", self.토큰())
        몸 = urllib.parse.urlencode(값, encoding="utf-8").encode()
        req = urllib.request.Request(self.바탕 + 길, data=몸)
        req.add_header("Content-Type", "application/x-www-form-urlencoded")
        req.add_header("Referer", self.바탕 + "/")
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
        """지금 어느 화면으로 보내지는가 — 「/」 를 눌러 최종 자리를 본다."""
        _, 주소, _ = self.보기("/")
        return urllib.parse.urlparse(주소).path

    def 들어가기(self, 길: str, 비번: str) -> tuple[int, str]:
        """화면 하나를 연다. 비밀번호를 한 번 더 묻거든 대답하고 다시 연다.

        계정 화면처럼 위험한 자리는 로그인만으로 열리지 않는다 (재확인 벽).
        이것을 모르면 「선생님이 안 만들어진다」고 엉뚱한 데를 뒤지게 된다 —
        실제로 그렇게 헛짚었다.
        """
        코드, 주소, h = self.보기(길)
        if urllib.parse.urlparse(주소).path == "/reauth":
            self.보내기("/reauth", {"password": 비번, "next": 길})
            코드, _, h = self.보기(길)
        return 코드, h


def 글만(h: str) -> str:
    h = re.sub(r"(?is)<(script|style|svg)[^>]*>.*?</\1>", " ", h)
    return re.sub(r"\s+", " ", re.sub(r"(?s)<[^>]+>", " ", h)).strip()


# ── 서버를 띄웠다 내린다 ────────────────────────────────────

def 빈포트() -> int:
    """되도록 늘 같은 번호를 쓴다 — 주소를 외워두고 쓰실 수 있게."""
    for 후보 in (8766, 8767, 8768):
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
    열쇠 = "".join(random.choices(string.ascii_letters + string.digits, k=64))
    환경 = {**os.environ, "MAJUNG_DATA": str(자료), "MAJUNG_SECRET": 열쇠,
            "PYTHONUTF8": "1", "PYTHONIOENCODING": "utf-8",
            "PYTHONPATH": str(뿌리 / "src")}

    # 1) 유치원을 연다 — 시범 운영 때와 똑같은 명령이다
    이름, 아이디, 비번 = 관리자
    난 = subprocess.run(
        [sys.executable, "-m", "firstout.main", "--setup-only",
         "--open-kinder", 유치원, "--admin", f"{이름}:{아이디}:{비번}"],
        cwd=str(뿌리), env=환경, capture_output=True, text=True,
        encoding="utf-8", errors="replace")
    if 난.returncode != 0:
        raise 걸림("유치원을 열지 못했습니다:\n" + 난.stdout + 난.stderr)

    # 2) 서버
    서버 = subprocess.Popen(
        [sys.executable, "-m", "uvicorn", "firstout.main:app",
         "--host", "127.0.0.1", "--port", str(포트), "--log-level", "warning"],
        cwd=str(뿌리), env=환경, stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT, text=True, encoding="utf-8", errors="replace")

    바탕 = "http://127.0.0.1:" + str(포트)
    for _ in range(60):
        if 서버.poll() is not None:
            raise 걸림("서버가 곧바로 죽었습니다:\n" + (서버.stdout.read() if 서버.stdout else ""))
        try:
            urllib.request.urlopen(바탕 + "/health", timeout=2)
            return 서버, 바탕
        except OSError:
            time.sleep(0.5)
    서버.kill()
    raise 걸림("서버가 일어나지 않았습니다")


# ── 걸어 본다 ───────────────────────────────────────────────

def 걷기(바탕: str, 말: list[str]) -> None:
    def 확인(맞나: bool, 무엇: str, 왜: str = "") -> None:
        if 맞나:
            print(좋음 + " " + 무엇)
        else:
            print(나쁨 + " " + 무엇 + ("  — " + 왜 if 왜 else ""))
            말.append(무엇 + ("  — " + 왜 if 왜 else ""))

    원장 = 손님(바탕)
    _, 아이디, 첫비번 = 관리자

    # 0 ─ 로그인 전에 볼 수 있는 것
    # 선생님이 이 프로그램을 처음 만나는 자리다. 여기서 안내를 못 보면
    # 「뭘 하는 건지」 모른 채 아이디부터 받아 들게 된다.
    print("\n── 0. 로그인 전 ──────────────────────────")
    코드, _, h = 원장.보기("/signin")
    확인(코드 == 200 and "손잡고" in h, "로그인 화면이 뜬다", str(코드))
    확인('href="/help"' in h, "로그인 화면에서 사용 안내로 갈 수 있다")
    확인('class="login-help"' in h and h.index("login-help") < h.index("</form>"),
         "안내 단추가 로그인 카드 안에 있다")

    # 결을 고쳐 올려도 브라우저가 예전 것을 붙들고 있으면 아무 소용이 없다
    표 = re.search(r"/static/app\.css\?v=([0-9a-f]{8})", h)
    확인(bool(표), "화면 결 주소에 바뀜표가 붙는다")
    if 표:
        코드, _, css = 원장.보기("/static/app.css?v=" + 표.group(1))
        확인(코드 == 200 and ".login-help" in css, "그 주소로 결이 내려온다", str(코드))

    코드, 주소, hh = 원장.보기("/help")
    확인(코드 == 200 and urllib.parse.urlparse(주소).path == "/help",
         "안내는 로그인 없이 열린다", "로그인 화면으로 쫓겨납니다")
    확인("서명" in hh and "체크" in hh, "안내에 알맹이가 들어 있다")
    확인("data-print-teacher" in hh and "data-print>" in hh,
         "인쇄 단추가 둘 (선생님용 · 전체)")
    확인(hh.count("data-admin") == 2,
         "총괄 관리자만 하는 대목이 표시되어 있다 (선생님용에서 빠진다)",
         str(hh.count("data-admin")) + "군데")
    확인("로그인하지 않고 보고 계십니다" in hh, "로그인 전이라는 것을 알려준다")
    확인("1차 개별" in hh, "귀가 차수를 보기로라도 보여준다")
    # 남의 원 자료가 새면 안 된다 — 안내에는 이름이 하나도 없어야 한다
    확인(유치원 not in hh and 관리자[0] not in hh,
         "로그인 전 안내에는 원 이름도 사람 이름도 없다")

    # 1 ─ 들어가기
    print("\n── 1. 들어가기 ───────────────────────────")

    원장.보내기("/signin", {"login_id": 아이디, "password": "틀린비번"})
    확인(원장.어디() == "/signin", "틀린 비밀번호로는 들어가지 못한다")

    코드, _, _ = 원장.보내기("/signin", {"login_id": 아이디,
                                     "password": 첫비번, "device": "shared"})
    확인(코드 == 200, 아이디 + " / " + 첫비번 + " 로 들어간다", str(코드))

    # 2 ─ 첫 비밀번호
    print("\n── 2. 첫 비밀번호 ────────────────────────")
    자리 = 원장.어디()
    확인(자리 == "/me/password",
         "1234 인 채로는 아무 화면도 못 본다 (비밀번호 화면에 붙잡는다)",
         "지금 자리가 " + 자리)

    원장.보내기("/me/password", {"current": 첫비번, "password": "12", "password2": "12"})
    확인(원장.어디() == "/me/password", "너무 짧은 비밀번호는 안 받는다")

    원장.보내기("/me/password", {"current": 첫비번, "password": 새비번, "password2": 새비번})
    자리 = 원장.어디()
    확인(자리 != "/me/password", "새 비밀번호를 정하면 풀려난다", "아직 " + 자리)

    # 3 ─ 반
    print("\n── 3. 반 만들기 ──────────────────────────")
    코드, _, h = 원장.보기("/settings")
    확인(코드 == 200, "설정 화면이 뜬다", str(코드))
    원장.보내기("/settings/class/add", {"name": "해님반"})
    _, _, h = 원장.보기("/settings")
    확인("해님반" in h, "「해님반」 이 생겼다")

    _, _, h = 원장.보기("/roster")
    후보 = re.findall(r'<option value="(\d+)"[^>]*>\s*해님반', h)
    반번호 = 후보[0] if 후보 else ""
    확인(bool(반번호), "명부 화면에서 새 반을 고를 수 있다")

    # 4 ─ 선생님
    print("\n── 4. 선생님 더하기 ──────────────────────")
    샘이름, 샘아이디 = 선생님
    _, 주소, _ = 원장.보기("/users")
    확인(urllib.parse.urlparse(주소).path == "/reauth",
         "계정 화면은 비밀번호를 한 번 더 묻는다", "그냥 열립니다")
    코드, h = 원장.들어가기("/users", 새비번)
    확인(코드 == 200 and "선생님" in 글만(h), "대답하면 계정 화면이 열린다", str(코드))
    원장.보내기("/users/add", {"name": 샘이름, "login_id": 샘아이디,
                            "title": "담임", "class_id": 반번호, "role": "선생님"})
    _, h = 원장.들어가기("/users", 새비번)
    확인(샘이름 in h, 샘이름 + " 선생님이 목록에 보인다")
    확인("담임" in h, "직함이 「담임」 으로 적힌다")

    번호 = re.findall(r"/users/(\d+)/invite", h)
    초대길 = ""
    if 번호:
        _, _, ih = 원장.보내기("/users/" + 번호[-1] + "/invite", {})
        찾 = re.search(r"/join/([A-Za-z0-9_\-\.]+)", ih)
        초대길 = "/join/" + 찾.group(1) if 찾 else ""
    확인(bool(초대길), "초대 링크가 만들어진다")

    # 5 ─ 아이
    print("\n── 5. 아이 올리기 ────────────────────────")
    for 아이, 보호자, 사이, 전화 in 아이들:
        원장.보내기("/roster/add", {"name": 아이, "class_id": 반번호,
                                 "g_name": 보호자, "g_relation": 사이,
                                 "g_phone": 전화})
    _, _, h = 원장.보기("/roster")
    보인다 = [아이 for 아이, *_ in 아이들 if 아이 in h]
    확인(len(보인다) == len(아이들),
         "아이 " + str(len(아이들)) + "명이 명부에 오른다", "보이는 건 " + str(보인다))

    아이번호 = re.findall(r'/child/(\d+)"', h)
    확인(bool(아이번호), "명부에서 아이 화면으로 넘어갈 수 있다")
    첫아이 = 아이번호[0] if 아이번호 else ""

    ch = ""
    if 첫아이:
        _, _, ch = 원장.보기("/child/" + 첫아이)
        확인(any(g in ch for _, g, *_ in 아이들), "아이 화면에 보호자가 함께 보인다")

    # 6 ─ 주간 계획
    print("\n── 6. 주간 귀가 계획 ─────────────────────")
    차수 = re.findall(r'value="r:(\d+)"', ch)
    확인(bool(차수), "귀가 차수를 고를 수 있다")
    if 차수 and 첫아이:
        for 요일 in range(5):
            원장.보내기("/child/" + 첫아이 + "/plan",
                      {"weekday": str(요일), "how": "r:" + 차수[0]})
        _, _, ch2 = 원장.보기("/child/" + 첫아이)
        정해짐 = len(re.findall(r'value="r:' + 차수[0] + r'"[^>]*selected', ch2))
        확인(정해짐 >= 5, "월~금 다섯 칸이 정해진다", "정해진 칸 " + str(정해짐) + "개")

    # 7 ─ 명단
    # 주간 계획은 월~금만 있다. 오늘이 주말이면 명단이 비는 것이 **맞는 동작**이라,
    # 그 날 돌리면 시나리오가 통째로 못 지나간다. 평일 하루를 골라 본다.
    오늘 = dt.date.today()
    보는날 = 오늘 + dt.timedelta(days=(7 - 오늘.weekday()) % 7) if 오늘.weekday() >= 5 else 오늘
    날 = 보는날.isoformat()
    print("\n── 7. 명단 (" + 날 + " " + "월화수목금토일"[보는날.weekday()] + "요일) ──────")
    찾은키, 찾은h = "", ""
    for 키 in ("i1", "b1", "b2", "i2", "care"):
        코드, _, lh = 원장.보기("/list/" + 키 + "?d=" + 날)
        if 코드 == 200 and 아이들[0][0] in lh:
            찾은키, 찾은h = 키, lh
            break
    확인(bool(찾은키), "정해준 차수의 명단에 " + 아이들[0][0] + " 이가 나온다",
         "어느 명단에도 안 보입니다")

    # 8 ─ 귀가 체크
    print("\n── 8. 귀가 체크 ──────────────────────────")
    if 찾은키 and 첫아이:
        서명필요 = "signature" in 찾은h
        길 = "/list/" + 찾은키 + "/" + 첫아이

        def 체크() -> None:
            if 서명필요:
                원장.보내기(길 + "/sign",
                          {"receiver": "default", "receiver_name": 아이들[0][1],
                           "receiver_rel": 아이들[0][2],
                           "signature": "data:image/png;base64,iVBORw0KGgo=",
                           "memo": "", "d": 날})
            else:
                원장.보내기(길 + "/check", {"how": "", "d": 날})

        확인(서명필요, "서명이 필요한 차수는 서명 칸이 함께 뜬다", "서명 없이 체크하는 차수입니다")
        전 = 찾은h.count("/undo")
        체크()
        _, _, lh = 원장.보기("/list/" + 찾은키 + "?d=" + 날)
        확인(lh.count("/undo") > 전, "체크하면 되돌릴 수 있는 상태로 바뀐다")

        원장.보내기(길 + "/undo", {"d": 날})
        _, _, lh = 원장.보기("/list/" + 찾은키 + "?d=" + 날)
        확인(lh.count("/undo") == 전, "잘못 눌렀을 때 되돌려진다")
        체크()
    else:
        print("  · 명단이 없어 체크는 건너뜁니다")

    # 9 ─ 반별 현황
    print("\n── 9. 반별 현황 ──────────────────────────")
    코드, _, bh = 원장.보기("/board?d=" + 날)
    확인(코드 == 200, "반별 현황이 뜬다", str(코드))
    확인("해님반" in bh, "새로 만든 반이 현황에 나온다")
    확인("귀가 진행률" in bh, "「진행」 이 아니라 「귀가 진행률」 로 적혀 있다")
    if 찾은키:
        # 진행률은 띠 그림이고, 숫자는 그 띠의 설명글에 들어 있다
        띠 = re.search(r'title="귀가 (\d+) · 현원 (\d+) · 결석조퇴 (\d+)"', bh)
        확인(bool(띠) and 띠.group(1) == "1" and 띠.group(2) == "2",
             "체크한 한 명이 현황에 반영된다 (귀가 1 · 현원 2)",
             띠.group(0) if 띠 else "현황 숫자를 못 찾았습니다")

    # 10 ─ 선생님이 들어온다
    print("\n── 10. 선생님이 들어온다 ─────────────────")
    if 초대길:
        샘 = 손님(바탕)
        코드, _, _ = 샘.보기(초대길)
        확인(코드 == 200, "초대 링크가 열린다", str(코드))
        샘.보내기(초대길, {"password": 새비번, "password2": 새비번, "device": "personal"})
        코드, _, sh = 샘.보기("/board")
        확인(코드 == 200 and "해님반" in sh, "선생님이 자기 원 화면을 본다", str(코드))
        _, 주소, _ = 샘.보기("/users")
        확인(urllib.parse.urlparse(주소).path != "/users",
             "선생님은 계정 화면에 못 들어간다", "들어가집니다")
        if 찾은키:
            코드, _, lh2 = 샘.보기("/list/" + 찾은키 + "?d=" + 날)
            확인(코드 == 200 and 아이들[0][0] in lh2, "선생님도 같은 명단을 본다", str(코드))

    # 10-2 ─ 로그인한 뒤의 안내
    print("\n── 10-2. 로그인 뒤의 안내 ────────────────")
    코드, _, hh = 원장.보기("/help")
    확인(코드 == 200, "안내가 뜬다", str(코드))
    확인("로그인하지 않고 보고 계십니다" not in hh, "로그인했으면 그 쪽지는 사라진다")
    확인("지금 우리 원의 귀가 차수" in hh, "우리 원의 차수로 바뀐다")

    # 11 ─ 남는 기록
    print("\n── 11. 남는 기록 ─────────────────────────")
    코드, _, ah = 원장.보기("/audit")
    확인(코드 == 200, "감사 로그가 뜬다", str(코드))
    확인(선생님[0] in ah or 아이들[0][0] in ah or "등록" in 글만(ah),
         "방금 한 일이 기록에 남는다")


def 손으로(바탕: str) -> None:
    """자리만 깔아 두고 기다린다 — 사람이 직접 눌러보게."""
    이름, 아이디, 비번 = 관리자
    print()
    print("  ──────────────────────────────────────────────")
    print("   " + 바탕 + "   ← 여기를 여세요")
    print("  ──────────────────────────────────────────────")
    print()
    print("   유치원 : " + 유치원)
    print("   들어가기: " + 아이디 + " / " + 비번 + "   (" + 이름 + " · 총괄 관리자)")
    print()
    print("   반·귀가 차수·학원은 채워져 있고, 원아는 비어 있습니다")
    print("   — 시범 운영 첫날과 똑같은 상태입니다.")
    print()
    print("   끝내려면 Ctrl+C  →  연습한 자료는 그때 모두 지워집니다.")
    print()
    try:
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        print()
        print("  끝냅니다.")


def main() -> int:
    직접 = "--손으로" in sys.argv or "--hand" in sys.argv
    자료 = Path(tempfile.mkdtemp(prefix="majung-scenario-"))
    말: list[str] = []
    서버 = None
    print()
    print("  자리를 깝니다 — 임시 자료 폴더를 쓰고 끝나면 지웁니다"
          if 직접 else
          "  실제 화면을 눌러 봅니다 — 임시 자료 폴더를 쓰고 끝나면 지웁니다")
    print("  임시 자리: " + str(자료))
    try:
        서버, 바탕 = 서버_띄우기(자료)
        if 직접:
            손으로(바탕)
        else:
            print("  서버: " + 바탕)
            걷기(바탕, 말)
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
        for _ in range(10):        # 윈도우는 파일을 놓는 데 잠깐 걸린다
            shutil.rmtree(자료, ignore_errors=True)
            if not 자료.exists():
                break
            time.sleep(0.5)
        print("\n  임시 자료: " + ("아직 남아 있습니다" if 자료.exists() else "지웠습니다"))

    print()
    if 직접:
        return 0
    if 말:
        print("  걸린 것 " + str(len(말)) + "개")
        for m in 말:
            print("    - " + m)
        print()
        return 1
    print("  시나리오가 처음부터 끝까지 지나갑니다.")
    print()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
