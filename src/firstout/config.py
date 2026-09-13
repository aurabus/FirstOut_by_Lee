"""경로와 기본값."""

from __future__ import annotations

import os
from pathlib import Path

# 데이터는 저장소 밖이 아니라 프로젝트 안 data/ 에 둔다.
# .gitignore 로 커밋이 차단되어 있으므로 원아 정보가 저장소에 올라가지 않는다.
BASE_DIR = Path(__file__).resolve().parent
PKG_DIR = BASE_DIR
PROJECT_DIR = BASE_DIR.parent.parent

DATA_DIR = Path(os.environ.get("MAJUNG_DATA", PROJECT_DIR / "data"))
BACKUP_DIR = DATA_DIR / "backup"
UPLOAD_DIR = DATA_DIR / "uploads"
DB_PATH = DATA_DIR / "majung.db"

TEMPLATE_DIR = PKG_DIR / "templates"
STATIC_DIR = PKG_DIR / "static"


def _static_ver() -> str:
    """화면 결이 바뀌었는지 알려주는 짧은 표.

    브라우저는 한 번 받은 /static/app.css 를 서버에 다시 묻지 않고 그냥 쓴다.
    그래서 화면을 고쳐 올려도 **쓰는 사람 눈에는 예전 화면**이 남는다.
    실제로 새 단추가 카드 옆에 엉뚱하게 붙어 보였고, 서버는 멀쩡한데 한참을
    찾았다. 주소 뒤에 이 표를 붙여 두면, 파일이 바뀐 날에만 주소가 바뀌어
    브라우저가 새로 받아 간다. 안 바뀐 날에는 그대로 캐시를 쓴다.
    """
    import hashlib

    h = hashlib.sha256()
    for 이름 in ("aurabus.css", "app.css", "app.js"):
        f = STATIC_DIR / 이름
        try:
            h.update(f.read_bytes())
        except OSError:      # 없으면 없는 대로 — 여기서 서버가 죽을 일은 아니다
            h.update(이름.encode())
    return h.hexdigest()[:8]


STATIC_VER = _static_ver()

# 서비스 주소. 회사 서버에 올려 서브도메인으로 열 때 반드시 정해야 한다.
#     $env:MAJUNG_PUBLIC_URL = "https://majung.aurabus.co.kr"
# 비워두면 원내망 주소(192.168.x.x)를 안내한다 — 시험·시연용이다.
PUBLIC_URL = os.environ.get("MAJUNG_PUBLIC_URL", "").rstrip("/")

# 앞에 우리가 세운 프록시(nginx 등)가 몇 대인가.
#     $env:MAJUNG_PROXY_HOPS = "1"
# X-Forwarded-For 는 **아무나 보낼 수 있는 헤더**다. 그 첫 값을 믿으면 접속지를
# 마음대로 꾸며낼 수 있어, 속도 제한이 무력해지고 감사 로그의 접속지가 거짓이 된다.
# 그래서 「우리 프록시가 붙인 자리」만 본다. 0 이면 헤더를 아예 믿지 않는다.
try:
    PROXY_HOPS = max(0, int(os.environ.get("MAJUNG_PROXY_HOPS", "0")))
except ValueError:
    PROXY_HOPS = 0

# 화면의 결. 비워두면 기본(숲). aurabus.css 에 담긴 것: mist · moss · blank
#     $env:MAJUNG_SKIN = "mist"
SKIN = os.environ.get("MAJUNG_SKIN", "").strip().lower()

APP_NAME = "손잡고 마중"
APP_TAGLINE = "아이를 안전하게, 집으로"

# 세션 서명 키. 이 값을 아는 사람은 남의 로그인 세션을 만들어낼 수 있으므로
# 운영에서는 반드시 환경변수로 덮어써야 한다. main 에서 확인하고 막는다.
DEV_SECRET = "majung-dev-secret-change-me"

# 빈 값은 「안 정한 것」으로 본다.
#     MAJUNG_SECRET=          ← Container Manager 에서 값을 안 채우면 이렇게 온다
# 예전에는 이것이 검사를 그냥 통과해 **빈 키로 세션에 서명**했다. 기본 키보다 나쁘다.
_주어진키 = os.environ.get("MAJUNG_SECRET", "").strip()
SECRET_KEY = _주어진키 or DEV_SECRET
IS_DEV_SECRET = SECRET_KEY == DEV_SECRET

# 짧은 키는 세우기는 하되 알려준다. 32자면 넉넉하다.
MIN_SECRET = 32
SECRET_TOO_SHORT = not IS_DEV_SECRET and len(SECRET_KEY) < MIN_SECRET

WEEKDAYS = ["월", "화", "수", "목", "금"]


def ensure_dirs() -> None:
    for d in (DATA_DIR, BACKUP_DIR, UPLOAD_DIR):
        d.mkdir(parents=True, exist_ok=True)
