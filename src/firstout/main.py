"""손잡고 마중 — 서버 진입점.

원무실 PC 한 대가 서버가 되고, 선생님 기기는 브라우저로 접속한다.
    python -m firstout.main            개발 실행
    majung                             설치 후 명령어
"""

from __future__ import annotations

import argparse
import datetime as dt
import mimetypes
import socket

from fastapi import Depends, FastAPI, Request
from fastapi.responses import RedirectResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from sqlalchemy.orm import Session

from . import service
from .config import APP_NAME, APP_TAGLINE, STATIC_DIR, TEMPLATE_DIR, WEEKDAYS, ensure_dirs
from .db import SessionLocal, get_db, init_db
from .models import Teacher
from .security import read_token
from .seed import seed_base

# Windows 기본 목록에 woff2 가 없어 octet-stream 으로 나가므로 직접 등록한다
mimetypes.add_type("font/woff2", ".woff2")

app = FastAPI(title=APP_NAME, docs_url=None, redoc_url=None)
app.mount("/static", StaticFiles(directory=STATIC_DIR), name="static")
templates = Jinja2Templates(directory=str(TEMPLATE_DIR))

DAY_KO = ["월", "화", "수", "목", "금", "토", "일"]


def today() -> dt.date:
    return dt.date.today()


def pick_date(d: str = "") -> dt.date:
    """조회 날짜. 지난 기록을 다시 볼 때 쓴다 (?d=2026-09-07)."""
    if d:
        try:
            return dt.date.fromisoformat(d)
        except ValueError:
            pass
    return today()


def now() -> dt.datetime:
    return dt.datetime.now()


def current_teacher(request: Request, db: Session) -> Teacher | None:
    tid = read_token(request.cookies.get("majung"))
    return db.get(Teacher, tid) if tid else None


def page(request: Request, name: str, db: Session, teacher: Teacher | None, **ctx):
    """모든 화면이 공통으로 쓰는 값을 채워 렌더한다."""
    d = ctx.pop("day", None) or today()
    base = {
        "request": request,
        "app_name": APP_NAME,
        "tagline": APP_TAGLINE,
        "setting": service.setting(db),
        "me": teacher,
        "today": d,
        "day": d,
        "day_ko": f"{d.month}월 {d.day}일 ({DAY_KO[d.weekday()]})",
        "today_ko": f"{d.month}월 {d.day}일 ({DAY_KO[d.weekday()]})",
        "is_today": d == today(),
        "prev_day": (d - dt.timedelta(days=1)).isoformat(),
        "next_day": (d + dt.timedelta(days=1)).isoformat(),
        "weekdays": WEEKDAYS,
        "classes": service.classes(db),
        "rounds": service.rounds(db),
        "now": now(),
    }
    base.update(ctx)
    return templates.TemplateResponse(request, name, base)


@app.on_event("startup")
def _startup() -> None:
    ensure_dirs()
    init_db()
    with SessionLocal() as db:
        seed_base(db)


@app.get("/health")
def health() -> dict[str, str]:
    """선생님 화면 상단의 「서버 연결됨」 표시가 이 주소를 확인한다."""
    return {"status": "ok", "time": now().strftime("%H:%M:%S")}


@app.get("/")
def home(request: Request, db: Session = Depends(get_db)):
    me = current_teacher(request, db)
    if me is None:
        return RedirectResponse("/login", status_code=303)
    return RedirectResponse("/board", status_code=303)


# 라우터는 아래에서 등록한다 (순환 참조를 피하려고 마지막에 둔다)
from .web import auth, board, lists, roster, settings_page  # noqa: E402

for mod in (auth, board, lists, roster, settings_page):
    app.include_router(mod.router)


def local_ip() -> str:
    """선생님들에게 알려줄 접속 주소를 찾는다."""
    try:
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        s.connect(("8.8.8.8", 80))
        ip = s.getsockname()[0]
        s.close()
        return ip
    except OSError:
        return "127.0.0.1"


def main() -> None:
    import uvicorn

    ap = argparse.ArgumentParser(description="손잡고 마중 서버")
    ap.add_argument("--host", default="0.0.0.0")
    ap.add_argument("--port", type=int, default=8000)
    ap.add_argument("--reload", action="store_true", help="코드를 고치면 자동으로 다시 읽는다")
    ap.add_argument("--demo", action="store_true", help="시연용 가상 원아를 넣는다")
    ap.add_argument("--reset", action="store_true", help="자료를 모두 지우고 처음부터 (주의)")
    ap.add_argument("--open", action="store_true", help="브라우저를 함께 연다")
    args = ap.parse_args()

    ensure_dirs()

    if args.reset:
        from .config import DB_PATH

        for suffix in ("", "-wal", "-shm"):
            f = DB_PATH.with_name(DB_PATH.name + suffix)
            if f.exists():
                f.unlink()
        print("자료를 모두 지웠습니다.")

    init_db()
    with SessionLocal() as db:
        seed_base(db)
        if args.demo:
            from .seed import seed_demo

            made = seed_demo(db)
            print(f"시연용 원아 {made}명 생성" if made else "원아가 이미 있어 건너뜀")

    # 주말에는 주간 계획이 없어 명단이 비므로, 가장 가까운 평일을 함께 알려준다
    d = today()
    hint = ""
    if d.weekday() > 4:
        weekday = d - dt.timedelta(days=d.weekday() - 4)
        hint = f"  오늘은 주말입니다 — 화면에서 「어제」를 누르거나 ?d={weekday} 로 평일을 보세요\n"

    url = f"http://127.0.0.1:{args.port}"
    print(f"\n  {APP_NAME} — {APP_TAGLINE}")
    print(f"  이 PC        {url}")
    print(f"  선생님 기기   http://{local_ip()}:{args.port}")
    print("  로그인 PIN    0000  (설정에서 바꾸세요)")
    if hint:
        print(hint, end="")
    print()

    if args.open:
        import threading
        import webbrowser

        threading.Timer(1.2, lambda: webbrowser.open(url)).start()

    uvicorn.run("firstout.main:app", host=args.host, port=args.port, reload=args.reload)


if __name__ == "__main__":
    main()
