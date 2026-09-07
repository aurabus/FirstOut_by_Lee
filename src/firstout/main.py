"""손잡고 마중 — 서버 진입점.

원무실 PC 한 대가 서버가 되고, 선생님 기기는 브라우저로 접속한다.
    python -m firstout.main            개발 실행
    majung                             설치 후 명령어
"""

from __future__ import annotations

import argparse
import datetime as dt
import mimetypes
import sys

from fastapi import Depends, FastAPI, Request
from fastapi.responses import RedirectResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from sqlalchemy.orm import Session

from . import flash, service
from .config import (
    APP_NAME,
    APP_TAGLINE,
    IS_DEV_SECRET,
    STATIC_DIR,
    TEMPLATE_DIR,
    WEEKDAYS,
    ensure_dirs,
)
from .csrf import AuditMiddleware, CSRFMiddleware
from .db import SessionLocal, get_db, init_db
from .models import User
from .security import CSRF_COOKIE, new_csrf, pw_stamp, read_token

# Windows 기본 목록에 woff2 가 없어 octet-stream 으로 나가므로 직접 등록한다
mimetypes.add_type("font/woff2", ".woff2")

app = FastAPI(title=APP_NAME, docs_url=None, redoc_url=None)
# 감사 로그가 바깥에 있어야 차단된 요청까지 남는다
app.add_middleware(CSRFMiddleware)
app.add_middleware(AuditMiddleware)
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


RUN_PORT: int = 0   # 실행 포트 — 접속 안내 화면이 쓴다


def is_secure(request: Request) -> bool:
    """리버스 프록시 뒤에서는 요청이 http 로 보인다.

    그대로 판단하면 secure 쿠키가 영영 걸리지 않아, 비밀번호로 지킨 세션이
    평문으로 새어 나갈 수 있다. 프록시가 알려주는 원래 방식을 함께 본다.
    """
    fwd = request.headers.get("x-forwarded-proto", "")
    return request.url.scheme == "https" or fwd.split(",")[0].strip() == "https"


def current_user(request: Request, db: Session) -> User | None:
    got = read_token(request.cookies.get("majung"))
    if got is None:
        return None
    uid, stamp = got
    u = db.get(User, uid)
    if u is None or not u.active:
        return None
    # 비밀번호를 바꾸면 예전 로그인은 더 이상 통하지 않는다
    if stamp != pw_stamp(u.password_hash):
        return None
    # 승인 전이거나 중지된 유치원이면 들여보내지 않는다
    if u.kinder_id is not None and (u.kinder is None or not u.kinder.usable):
        return None
    return u


# 예전 이름 — 화면 코드가 아직 쓰는 곳이 있어 남겨둔다
current_teacher = current_user


def page(request: Request, name: str, db: Session, teacher: User | None, **ctx):
    """모든 화면이 공통으로 쓰는 값을 채워 렌더한다."""
    d = ctx.pop("day", None) or today()
    base = {
        "request": request,
        "app_name": APP_NAME,
        "tagline": APP_TAGLINE,
        "me": teacher,
        "kinder": teacher.kinder if teacher else ctx.get("kinder"),
        "today": d,
        "day": d,
        "day_ko": f"{d.month}월 {d.day}일 ({DAY_KO[d.weekday()]})",
        "today_ko": f"{d.month}월 {d.day}일 ({DAY_KO[d.weekday()]})",
        "is_today": d == today(),
        "prev_day": (d - dt.timedelta(days=1)).isoformat(),
        "next_day": (d + dt.timedelta(days=1)).isoformat(),
        "weekdays": WEEKDAYS,
        "classes": service.classes(db, teacher.kinder_id) if teacher and teacher.kinder_id else [],
        "rounds": service.rounds(db, teacher.kinder_id) if teacher and teacher.kinder_id else [],
        "now": now(),
        "csrf": request.cookies.get(CSRF_COOKIE) or new_csrf(),
    }
    # 처리 결과 안내는 주소가 아니라 쿠키로 온다 (원아 이름이 로그에 남지 않게)
    fmsg, fsecret = flash.take(request)
    base.setdefault("msg", "")
    if fmsg:
        base["msg"] = fmsg
    if fsecret:
        base["new_pw"] = fsecret

    base.update({k: v for k, v in ctx.items() if k not in ("msg",) or v})
    res = templates.TemplateResponse(request, name, base)
    if fmsg or fsecret:
        flash.clear(res)
    if not request.cookies.get(CSRF_COOKIE):
        res.set_cookie(
            CSRF_COOKIE, base["csrf"], httponly=False, samesite="lax",
            secure=is_secure(request), max_age=60 * 60 * 24 * 14,
        )
    return res


@app.on_event("startup")
def _startup() -> None:
    ensure_dirs()
    init_db()
    with SessionLocal() as db:
        from . import audit

        gone = audit.purge_old(db)
        if gone:
            print(f"  감사 로그 {gone}건 정리 (한 달 지난 기록)")


@app.get("/health")
def health() -> dict[str, str]:
    """선생님 화면 상단의 「서버 연결됨」 표시가 이 주소를 확인한다."""
    return {"status": "ok", "time": now().strftime("%H:%M:%S")}


@app.get("/")
def home(request: Request, db: Session = Depends(get_db)):
    me = current_user(request, db)
    if me is None:
        return RedirectResponse("/signin", status_code=303)
    if me.must_change_pw:
        return RedirectResponse("/me/password", status_code=303)
    if me.is_operator:
        return RedirectResponse("/operator", status_code=303)
    return RedirectResponse("/board", status_code=303)


# 라우터는 아래에서 등록한다 (순환 참조를 피하려고 마지막에 둔다)
from .web import (  # noqa: E402
    audit_page,
    auth,
    board,
    connect,
    lists,
    operator,
    roster,
    settings_page,
    upload,
    users,
)

for mod in (
    audit_page, auth, board, connect, lists,
    operator, roster, settings_page, upload, users,
):
    app.include_router(mod.router)


def use_utf8_console() -> None:
    """한글 Windows 콘솔은 기본이 cp949 라 「—」 같은 글자에서 print 가 죽는다.

    배너 한 줄 때문에 서버가 아예 시작되지 않는 일이 있어, 출력 인코딩을 먼저 고정한다.
    콘솔 설정에 실패하더라도 errors="replace" 덕분에 죽지는 않는다.
    """
    if sys.platform == "win32":
        try:
            import ctypes

            ctypes.windll.kernel32.SetConsoleOutputCP(65001)
        except (AttributeError, OSError):
            pass
    for stream in (sys.stdout, sys.stderr):
        try:
            stream.reconfigure(encoding="utf-8", errors="replace")
        except (AttributeError, OSError, ValueError):
            pass


def main() -> None:
    import uvicorn

    use_utf8_console()

    ap = argparse.ArgumentParser(description="손잡고 마중 서버")
    ap.add_argument("--host", default="0.0.0.0")
    ap.add_argument("--port", type=int, default=8000)
    ap.add_argument("--reload", action="store_true", help="코드를 고치면 자동으로 다시 읽는다")
    ap.add_argument("--demo", action="store_true", help="시연용 가상 원아를 넣는다")
    ap.add_argument("--reset", action="store_true", help="자료를 모두 지우고 처음부터 (주의)")
    ap.add_argument("--open", action="store_true", help="브라우저를 함께 연다")
    ap.add_argument("--operator", metavar="아이디:비밀번호",
                    help="운영자 계정을 만든다 (서버를 처음 세울 때 한 번)")
    args = ap.parse_args()

    ensure_dirs()

    # 기본 서명 키로 외부에 열면 남의 로그인 세션을 만들어낼 수 있다. 아예 막는다.
    if IS_DEV_SECRET and args.host not in ("127.0.0.1", "localhost"):
        say = print
        say()
        say("  세션 서명 키가 기본값입니다.")
        say("  이대로 외부에 열면 남의 로그인 세션을 만들어낼 수 있습니다.")
        say("  환경변수를 정하고 다시 실행해 주세요.")
        say()
        say('      $env:MAJUNG_SECRET = "충분히 긴 임의의 문자열"')
        say()
        say("  (내 PC 에서만 시험하려면 --host 127.0.0.1)")
        say()
        return

    if args.reset:
        from .config import DB_PATH

        for suffix in ("", "-wal", "-shm"):
            f = DB_PATH.with_name(DB_PATH.name + suffix)
            if f.exists():
                f.unlink()
        print("자료를 모두 지웠습니다.")

    global RUN_PORT
    RUN_PORT = args.port

    init_db()
    with SessionLocal() as db:
        if args.operator:
            from .seed import seed_operator

            login_id, _, pw = args.operator.partition(":")
            if not pw:
                print("  --operator 아이디:비밀번호 형태로 넣어주세요")
                return
            if seed_operator(db, login_id, pw):
                print(f"  운영자 계정 생성: {login_id}")
            else:
                print("  운영자 계정이 이미 있습니다")

        if args.demo:
            from .seed import seed_demo, seed_demo_kinder

            k = seed_demo_kinder(db)
            made = seed_demo(db, k.id)
            if made:
                print(f"  {k.name}: 시연용 원아 {made}명 생성")
            _demo_users(db, k)

        kinders = service.kindergartens(db)

    _print_banner(args.port, kinders)

    if args.open:
        import threading
        import webbrowser

        url = f"http://127.0.0.1:{args.port}/connect"
        threading.Timer(1.2, lambda: webbrowser.open(url)).start()

    uvicorn.run("firstout.main:app", host=args.host, port=args.port, reload=args.reload)


def _demo_users(db, kinder) -> None:
    """시연용 계정 — 원장과 담임 한 명. 실제 운영에서는 가입과 사용자 관리로 만든다."""
    from sqlalchemy import select

    from .models import ROLE_OWNER, ROLE_TEACHER, ClassRoom, User
    from .security import hash_password

    if db.scalar(select(User).where(User.kinder_id == kinder.id)):
        return
    room = db.scalar(
        select(ClassRoom).where(ClassRoom.kinder_id == kinder.id).order_by(ClassRoom.seq)
    )
    db.add(User(kinder_id=kinder.id, login_id="wonjang", password_hash=hash_password("majung1234"),
                name="최영호", role=ROLE_OWNER, title="원장"))
    db.add(User(kinder_id=kinder.id, login_id="teacher1", password_hash=hash_password("majung1234"),
                name="김미영", role=ROLE_TEACHER, title="지혜1 담임",
                class_id=room.id if room else None))
    db.commit()
    print("  시연 계정: wonjang / teacher1  비밀번호 majung1234")


def _print_banner(port: int, kinders: list, file=None) -> None:
    """실행하자마자 접속 주소를 알 수 있어야 한다.

    설치 후 가장 많이 막히는 것이 "선생님들이 어떤 주소로 들어가나요?" 라서
    주소를 눈에 띄게, 여러 개면 전부 보여준다.
    """
    from . import net

    out = file or sys.stdout

    def say(text: str = "") -> None:
        print(text, file=out)

    urls = net.all_urls(port)
    line = "─" * 58

    say(f"\n  {line}")
    say(f"   {APP_NAME} — {APP_TAGLINE}")
    say(f"  {line}")
    say(f"   선생님 기기   {urls[0]}          ← 이 주소를 알려주세요")
    for u in urls[1:]:
        say(f"                 {u}")
    say(f"   이 PC         http://127.0.0.1:{port}")
    say(f"   접속 안내·QR   http://127.0.0.1:{port}/connect")
    say(f"  {line}")

    if kinders:
        names = " · ".join(f"{k.name}({k.status})" for k in kinders)
        say(f"   등록된 유치원  {len(kinders)}곳 — {names}")
    else:
        say("   등록된 유치원  없음 — /signup 에서 가입 신청을 받습니다")

    d = today()
    if d.weekday() > 4:
        weekday = d - dt.timedelta(days=d.weekday() - 4)
        say(f"   오늘은 주말   화면의 「어제」를 누르거나 {weekday} 로 평일을 보세요")
    say(f"  {line}\n")


if __name__ == "__main__":
    main()
