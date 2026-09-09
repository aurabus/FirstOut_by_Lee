"""화면 전수 점검 — 브라우저가 말없이 넘어가는 잘못을 찾는다.

표의 칸 수가 어긋나거나, 닫는 태그가 빠지거나, CSS 에 없는 class 를 쓰거나 해도
브라우저는 오류를 내지 않는다. 그냥 이상하게 그린다. 그래서 화면을 하나씩 열어
눈으로 볼 때마다 하나씩 나오는 일이 생긴다. 그럴 일이 아니라 한 번에 다 찾는다.

돌리는 법 — 서버를 띄워 두고::

    python tools/page_audit.py                       # http://127.0.0.1:8000
    python tools/page_audit.py http://127.0.0.1:8000

각 권한(운영자·관리자·선생님)으로 들어가 링크를 따라다니며 닿는 모든 화면을 본다.
"""

from __future__ import annotations

import http.cookiejar
import re
import sys
import urllib.error
import urllib.parse
import urllib.request
from html.parser import HTMLParser
from pathlib import Path

# 닫지 않는 태그
VOID = {"area", "base", "br", "col", "embed", "hr", "img", "input", "link",
        "meta", "param", "source", "track", "wbr"}
# 닫는 태그를 생략해도 되는 것들 — 안 닫혔다고 나무라지 않는다
OPTIONAL = {"li", "dt", "dd", "p", "option", "thead", "tbody", "tfoot", "tr", "td", "th"}

로그인 = [
    ("들어가기 전", "", ""),          # 로그인 화면·가입 화면도 화면이다
    ("운영자", "admin", "majung1234"),
    ("관리자", "wonjang", "majung1234"),
    ("선생님", "teacher1", "majung1234"),
]

# 링크가 아니라 form 으로만 닿는 화면이 있다 (초대 화면이 그렇다).
# 그런 곳도 GET 으로 열리는 화면이면 한 번 열어 본다.
시작점 = ("/", "/signin", "/signup", "/signup/done", "/login", "/pick")

# 사람이 보는 글에 나오면 안 되는 영문 주소 (감사 로그에서 한 번 걷어냈다)
영문주소 = re.compile(r"(?<![\w/])/(?:attend|board|roster|settings|users|list|child"
                      r"|audit|connect|upload|suggest|help|operator|signin|signup)\b")

# 크롤에서 뺄 길 — 파일로 내려받는 것, 나가는 것
건너뛰기 = ("/signout", "/roster/export", "/upload/template", "/openapi.json",
            "/sw.js", "/health", "/static", "/view/stop")


def _칸수(줄들: list[list[tuple[int, int]]]) -> list[int]:
    """rowspan 으로 아랫줄까지 내려오는 칸까지 세어, 줄마다 칸 수를 낸다."""
    내려오는: dict[int, int] = {}
    너비: list[int] = []
    for i, 칸들 in enumerate(줄들):
        w = 내려오는.pop(i, 0)
        for cs, rs in 칸들:
            w += cs
            for k in range(1, rs):
                내려오는[i + k] = 내려오는.get(i + k, 0) + cs
        너비.append(w)
    return 너비


class 뜯어보기(HTMLParser):
    """한 화면의 HTML 을 훑으며 잘못을 모은다."""

    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.탈: list[str] = []
        self.짝없음: list[str] = []
        self.안닫힘: list[str] = []
        self.아이디: dict[str, int] = {}
        self.가리킴: list[tuple[str, str]] = []      # (label for 같은 것, 가리키는 id)
        self.클래스: set[str] = set()
        self.표: list[list[int]] = []                # 표마다 줄별 칸 수
        self.바깥자원: list[str] = []
        self.글없는단추 = 0
        self.알트없는그림 = 0
        self.폼중첩 = False
        self.csrf없는폼: list[str] = []
        self.제목 = ""
        self._폼깊이 = 0
        self._현재폼: str | None = None
        self._폼에csrf = False
        self._표: list[list[tuple[int, int]]] | None = None
        self._줄: list[tuple[int, int]] | None = None
        self._글모으는곳: list[str] | None = None
        self._제목중 = False

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        a = {k: (v or "") for k, v in attrs}
        if tag not in VOID:
            self.탈.append(tag)

        if "id" in a:
            self.아이디[a["id"]] = self.아이디.get(a["id"], 0) + 1
        for 뭐 in ("for", "aria-labelledby", "aria-controls", "aria-describedby"):
            if a.get(뭐):
                for 하나 in a[뭐].split():
                    self.가리킴.append((f"{tag} {뭐}", 하나))
        for 이름 in a.get("class", "").split():
            self.클래스.add(이름)

        for 뭐 in ("src", "href", "srcset", "data-src"):
            v = a.get(뭐, "")
            if v.startswith(("http://", "https://", "//")):
                self.바깥자원.append(v.split("?")[0][:70])

        if tag == "form":
            self._폼깊이 += 1
            if self._폼깊이 > 1:
                self.폼중첩 = True
            self._현재폼 = a.get("action", "?")
            self._폼에csrf = a.get("method", "get").lower() != "post"
        if tag == "input" and a.get("name") == "_csrf":
            self._폼에csrf = True

        if tag == "img" and "alt" not in a:
            self.알트없는그림 += 1

        if tag == "table":
            self._표 = []
        if tag == "tr" and self._표 is not None:
            self._줄 = []
        if tag in ("td", "th") and self._줄 is not None:
            def 수(k: str) -> int:
                try:
                    return max(1, int(a.get(k, "1")))
                except ValueError:
                    return 1
            self._줄.append((수("colspan"), 수("rowspan")))

        if tag in ("button", "a") and self._글모으는곳 is None:
            # aria-label 이나 title 이 있으면 글자가 없어도 된다
            self._글모으는곳 = [a.get("aria-label", ""), a.get("title", "")]
        if tag == "title":
            self._제목중 = True

    def handle_data(self, data: str) -> None:
        if self._글모으는곳 is not None:
            self._글모으는곳.append(data)
        if self._제목중:
            self.제목 += data

    def handle_endtag(self, tag: str) -> None:
        if tag == "title":
            self._제목중 = False
        if tag in ("button", "a") and self._글모으는곳 is not None:
            if not "".join(self._글모으는곳).strip():
                self.글없는단추 += 1
            self._글모으는곳 = None
        if tag == "tr" and self._줄 is not None:
            if self._표 is not None:
                self._표.append(self._줄)
            self._줄 = None
        if tag == "table" and self._표 is not None:
            self.표.append(_칸수(self._표))
            self._표 = None
        if tag == "form":
            if self._폼깊이 > 0 and not self._폼에csrf:
                self.csrf없는폼.append(self._현재폼 or "?")
            self._폼깊이 = max(0, self._폼깊이 - 1)

        if tag in VOID:
            return
        if tag in self.탈:
            while self.탈:
                열린 = self.탈.pop()
                if 열린 == tag:
                    break
                if 열린 not in OPTIONAL:
                    self.안닫힘.append(열린)
        else:
            self.짝없음.append(tag)

    def 끝(self) -> None:
        self.안닫힘 += [t for t in self.탈 if t not in OPTIONAL and t != "html"]


def css_클래스() -> set[str]:
    static = Path(__file__).resolve().parent.parent / "src" / "firstout" / "static"
    글 = " ".join(
        re.sub(r"/\*.*?\*/", "", (static / n).read_text(encoding="utf-8"), flags=re.S)
        for n in ("aurabus.css", "app.css"))
    return set(re.findall(r"\.([^\W\d][\w-]*)", 글))


class _글만(HTMLParser):
    """태그를 걷어내고 사람 눈에 닿는 글만 남긴다.

    정규식으로 <...> 를 지우면 글 속의 부등호 하나에 밀려 엉뚱한 곳을 글로 센다.
    실제로 상단바의 href="/attend" 를 「사람 눈에 보이는 영문 주소」로 잘못 짚었다.
    """

    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.조각: list[str] = []
        self._건너뜀 = 0

    def handle_starttag(self, tag: str, attrs: object) -> None:
        if tag in ("script", "style", "template"):
            self._건너뜀 += 1

    def handle_endtag(self, tag: str) -> None:
        if tag in ("script", "style", "template") and self._건너뜀:
            self._건너뜀 -= 1

    def handle_data(self, data: str) -> None:
        if not self._건너뜀:
            self.조각.append(data)


def 보이는글(html: str) -> str:
    p = _글만()
    p.feed(html)
    p.close()
    return " ".join(p.조각)


class 손님:
    """한 사람이 브라우저를 들고 돌아다니는 것과 같다."""

    def __init__(self, base: str) -> None:
        self.base = base.rstrip("/")
        self.막힌길: dict[str, int] = {}
        self.문 = urllib.request.build_opener(
            urllib.request.HTTPCookieProcessor(http.cookiejar.CookieJar()))

    def 열기(self, 길: str) -> tuple[int, str, str]:
        # 주소에 한글이 들어 있으면 그대로는 보낼 수 없다 — 퍼센트로 바꿔서 보낸다
        바탕, _, 물음 = 길.partition("?")
        보낼길 = urllib.parse.quote(바탕, safe="/") + (
            "?" + urllib.parse.quote(물음, safe="=&") if 물음 else "")
        try:
            r = self.문.open(self.base + 보낼길, timeout=20)
            return r.status, r.headers.get("content-type", ""), r.read().decode("utf-8", "replace")
        except urllib.error.HTTPError as e:
            몸 = e.read().decode("utf-8", "replace")
            return e.code, e.headers.get("content-type", ""), 몸

    def 들어가기(self, 아이디: str, 비번: str) -> bool:
        _, _, h = self.열기("/signin")
        m = re.search(r'name="_csrf" value="([^"]+)"', h)
        if not m:
            return False
        몸 = urllib.parse.urlencode(
            {"_csrf": m.group(1), "login_id": 아이디, "password": 비번, "device": "personal"},
            encoding="utf-8").encode()
        self.문.open(urllib.request.Request(self.base + "/signin", data=몸), timeout=20)
        _, _, h = self.열기("/board")
        return "로그인" not in h[:400]

    def 한번더(self, 비번: str) -> bool:
        """비밀번호를 한 번 더 묻는 벽(재인증)을 넘는다.

        선생님 관리 같은 화면은 이 벽 뒤에 있다. 넘지 않으면 검사가 벽만 보고
        「이상 없음」이라고 말하게 된다 — 실제로 그랬다.
        """
        _, _, h = self.열기("/reauth")
        m = re.search(r'name="_csrf" value="([^"]+)"', h)
        if not m:
            return False
        몸 = urllib.parse.urlencode(
            {"_csrf": m.group(1), "next": "/users", "password": 비번},
            encoding="utf-8").encode()
        self.문.open(urllib.request.Request(self.base + "/reauth", data=몸), timeout=20)
        _, _, h = self.열기("/users")
        # 선생님에게는 선생님 관리 화면이 아예 없다 — 벽을 못 넘은 것과 다르다
        return "/invite" in h or "권한" in h or "오늘 현황" in h[:2000]

    def 둘러보기(self, 유치원: int) -> bool:
        """운영자가 그 유치원 안으로 들어가 본다 (보기만 한다)."""
        _, _, h = self.열기("/operator")
        m = re.search(r'name="_csrf" value="([^"]+)"', h)
        if not m:
            return False
        몸 = urllib.parse.urlencode({"_csrf": m.group(1)}, encoding="utf-8").encode()
        self.문.open(
            urllib.request.Request(f"{self.base}/operator/{유치원}/view", data=몸), timeout=20)
        _, _, h = self.열기("/board")
        return "로그인" not in h[:400]


def 모양(길: str) -> str:
    """같은 화면인지 가리는 잣대 — 물음표 뒤의 값이 아니라 이름만 본다.

    명단 화면에는 어제·내일로 가는 링크가 있어, 값까지 다르게 세면 날짜를 따라
    끝없이 돌게 된다. 실제로 그렇게 돌다가 멈추지 않았다.
    """
    바탕, _, 물음 = 길.partition("?")
    이름 = sorted(k for k, _ in urllib.parse.parse_qsl(물음))
    return 바탕 + ("?" + ",".join(이름) if 이름 else "")


def 돌아보기(c: 손님, get길: set[str], 최대: int = 400) -> dict[str, str]:
    """링크를 따라가며 닿는 모든 화면을 모은다.

    같은 모양의 화면은 몇 개만 본다 — 아이가 백 명이면 아이 화면도 백 개지만
    그것들은 같은 틀로 그려지므로 서너 개만 보면 잘못을 찾기에 넉넉하다.

    링크만 따라가면 못 가는 곳이 있다. 초대 화면은 「초대 만들기」를 눌러야
    닿는데, 그 주소는 GET 으로도 열린다. 그래서 form 이 가리키는 곳도
    GET 화면이면 한 번 열어 본다.
    """
    본것: dict[str, str] = {}
    본모양: dict[str, int] = {}
    갈곳 = list(시작점)
    while 갈곳 and len(본것) < 최대:
        길 = 갈곳.pop(0)
        if 길 in 본것 or 길 in c.막힌길 or 길.startswith(건너뛰기):
            continue
        m = 모양(길)
        if 본모양.get(m, 0) >= 3:
            continue
        본모양[m] = 본모양.get(m, 0) + 1
        코드, 종류, h = c.열기(길)
        if 코드 >= 400:
            c.막힌길[길] = 코드
            continue
        if "html" not in 종류:
            continue
        본것[길] = h
        for 뭐, 주소 in re.findall(r'(href|action)="([^"]+)"', h):
            주소 = 주소.split("#")[0]
            if not 주소 or 주소.startswith(("http", "mailto:", "tel:", "javascript:", "//")):
                continue
            if not 주소.startswith("/"):
                주소 = "/" + 주소
            if 뭐 == "action" and not _GET화면인가(주소, get길):
                continue                      # 보내기 전용 주소는 열어 봐야 405 다
            갈곳.append(주소)
    return 본것


def _GET화면인가(길: str, get길: set[str]) -> bool:
    바탕 = 길.split("?")[0]
    return any(re.match("^" + re.sub(r"\{[^}]+\}", r"[^/]+", p) + "$", 바탕) for p in get길)


def 살펴보기(누구: str, 길: str, h: str, 있는클래스: set[str]) -> list[str]:
    p = 뜯어보기()
    p.feed(h)
    p.close()
    p.끝()

    말: list[str] = []

    def 한마디(s: str) -> None:
        말.append(f"[{누구}] {길} — {s}")

    for i, 너비 in enumerate(p.표, 1):
        if len(set(너비)) > 1:
            한마디(f"{i}번째 표의 칸 수가 줄마다 다르다 {너비}")
    if p.안닫힘:
        한마디(f"닫히지 않은 태그: {sorted(set(p.안닫힘))}")
    if p.짝없음:
        한마디(f"열린 적 없는 닫는 태그: {sorted(set(p.짝없음))}")
    겹친id = sorted(k for k, n in p.아이디.items() if n > 1)
    if 겹친id:
        한마디(f"같은 id 가 두 번 이상: {겹친id}")
    빈가리킴 = sorted({f"{뭐}={i}" for 뭐, i in p.가리킴 if i not in p.아이디})
    if 빈가리킴:
        한마디(f"없는 id 를 가리킨다: {빈가리킴}")
    없는클래스 = sorted(c for c in p.클래스 if c not in 있는클래스)
    if 없는클래스:
        한마디(f"CSS 에 없는 class: {없는클래스}")
    if p.바깥자원:
        한마디(f"바깥 자원을 부른다: {sorted(set(p.바깥자원))}")
    if p.폼중첩:
        한마디("form 안에 form 이 있다 — 바깥 것이 보내지지 않는다")
    if p.csrf없는폼:
        한마디(f"_csrf 없는 보내기: {sorted(set(p.csrf없는폼))}")
    if p.글없는단추:
        한마디(f"글자도 이름표도 없는 단추/링크 {p.글없는단추}개")
    if p.알트없는그림:
        한마디(f"alt 없는 그림 {p.알트없는그림}개")
    if not p.제목.strip():
        한마디("<title> 이 비어 있다")
    영문 = sorted(set(영문주소.findall(보이는글(h))))
    if 영문:
        한마디(f"사람 눈에 영문 주소가 보인다: {영문}")
    for 흔적 in ("TODO", "FIXME", "lorem ipsum", "None", "undefined"):
        if re.search(rf">\s*{흔적}\s*<", h):
            한마디(f"화면에 「{흔적}」 이 그대로 남아 있다")
    return 말


def 모든길() -> set[str]:
    """프로그램이 가진 GET 화면의 목록. 어디를 못 가 봤는지 알려면 있어야 한다."""
    import os

    os.environ.setdefault("MAJUNG_SECRET", "audit-only")
    sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))
    try:
        import firstout.main as M
    except Exception:                                    # noqa: BLE001
        return set()
    길: set[str] = set()

    def 훑기(routes: object) -> None:
        for r in routes:                                 # type: ignore[union-attr]
            안쪽 = getattr(r, "original_router", None)
            if 안쪽 is not None:
                훑기(안쪽.routes)
                continue
            if "GET" in (getattr(r, "methods", None) or ()) and getattr(r, "path", None):
                길.add(r.path)

    훑기(M.app.routes)
    return 길


def 한바퀴(c: 손님, 누구: str, 있는클래스: set[str], 모든말: list[str],
          가본곳: set[str], get길: set[str]) -> int:
    화면들 = 돌아보기(c, get길)
    for 길, h in sorted(화면들.items()):
        가본곳.add(길.split("?")[0])
        모든말 += 살펴보기(누구, 길, h, 있는클래스)
    for 길, 코드 in sorted(c.막힌길.items()):
        모든말.append(f"[{누구}] {길} — 링크를 눌렀는데 {코드}")
    print(f"[{누구}] 화면 {len(화면들)}개")
    return len(화면들)


def 못가본곳(가본곳: set[str], get길: set[str]) -> list[str]:
    """링크를 따라가서는 닿지 못한 화면 — 검사에서 빠졌다는 뜻이다."""
    닮음 = [re.compile("^" + re.sub(r"\{[^}]+\}", r"[^/]+", p) + "$") for p in 가본곳]
    남은 = []
    for p in sorted(get길):
        if p.startswith(건너뛰기) or p in ("/", "/health", "/openapi.json"):
            continue
        본틀 = re.sub(r"\{[^}]+\}", r"[^/]+", p)
        if any(re.match("^" + 본틀 + "$", g) for g in 가본곳):
            continue
        if any(r.match(p) for r in 닮음):
            continue
        남은.append(p)
    return 남은


def main() -> int:
    base = sys.argv[1] if len(sys.argv) > 1 else "http://127.0.0.1:8000"
    있는클래스 = css_클래스()
    모든말: list[str] = []
    가본곳: set[str] = set()
    본화면 = 0

    get길 = 모든길()

    for 누구, 아이디, 비번 in 로그인:
        c = 손님(base)
        if 아이디 and not c.들어가기(아이디, 비번):
            print(f"[{누구}] {아이디} 로 들어가지 못했다 — 건너뛴다")
            continue
        # 선생님 관리 같은 화면은 비밀번호를 한 번 더 묻는 벽 뒤에 있다.
        # 운영자에게는 그런 화면이 없으므로 넘지 못해도 그만이다.
        if 아이디 and not c.한번더(비번) and 누구 != "운영자":
            print(f"[{누구}] 재인증 벽을 넘지 못했다 — 그 뒤 화면은 못 본다")
        본화면 += 한바퀴(c, 누구, 있는클래스, 모든말, 가본곳, get길)
        # 운영자는 유치원 안을 둘러보는 길이 하나 더 있다 — 그 화면들도 본다
        if 누구 == "운영자":
            if c.둘러보기(1):
                c.막힌길.clear()
                본화면 += 한바퀴(c, "운영자 둘러보기", 있는클래스, 모든말, 가본곳, get길)
            else:
                print("[운영자] 둘러보기로 들어가지 못했다")

    빠진곳 = 못가본곳(가본곳, get길)
    if 빠진곳:
        print()
        print("링크를 따라가서는 닿지 못한 화면 (눈으로 봐야 한다):")
        for p in 빠진곳:
            print("   ", p)

    print()
    if 본화면 < 20:
        # 로그인이 안 되면 몇 화면 못 보고 끝난다. 그걸 「이상 없음」이라고
        # 말하면 거짓말이 된다 — 아무것도 못 본 것과 다르지 않다.
        print(f"화면을 {본화면}개밖에 보지 못했습니다. 로그인이 안 된 것 같습니다.")
        print("이 검사기는 시연용 자료가 든 서버를 봅니다 (firstout --demo).")
        print("계정을 바꾸셨다면 tools/page_audit.py 의 「로그인」 목록을 고쳐주세요.")
        return 2

    if not 모든말:
        print(f"화면 {본화면}개 — 걸리는 것 없음")
        return 0
    print(f"화면 {본화면}개 · 걸린 것 {len(모든말)}개")
    print()
    for s in 모든말:
        print(" ·", s)
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
