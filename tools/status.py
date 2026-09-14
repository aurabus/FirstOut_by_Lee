"""지금 어떻게 쓰이고 있나 — 한 화면으로.

「잘 되고 있어?」에 답하려고 매번 이것저것 뒤지게 된다. 볼 것은 늘 같다:
누가 들어왔나, 아이는 올라갔나, 귀가는 처리되고 있나, 터진 데는 없나.

    python tools/status.py

읽기만 한다. 운영 자료를 열되 고치지 않는다.
"""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

뿌리 = Path(__file__).resolve().parent.parent

읽기 = '''
import datetime as dt, sqlite3, sys
sys.stdout.reconfigure(encoding="utf-8", errors="replace")
c = sqlite3.connect("file:/data/majung.db?mode=ro", uri=True)
하나 = lambda q, *a: c.execute(q, a).fetchone()
모두 = lambda q, *a: list(c.execute(q, a))

print("[유치원]")
for r in 모두("select name, status from kindergarten"):
    print("  %s · %s" % (r[0], r[1]))

print()
print("[계정]")
for r in 모두("select login_id, name, role, title, class_id, must_change_pw, "
              "last_login_at from user order by id"):
    아직 = " (아직 비밀번호를 안 바꿈)" if r[5] else ""
    언제 = str(r[6])[:16] if r[6] else "한 번도 안 들어옴"
    print("  %-8s %-6s %-5s %-10s 마지막 로그인 %s%s"
          % (r[0], r[1] or "", r[2] or "", r[3] or "", 언제, 아직))

print()
print("[자료]")
for 이름, 표 in (("반", "classroom"), ("귀가 차수", "round"), ("학원", "academy"),
                ("원아", "child"), ("보호자", "guardian"),
                ("주간 계획", "plan_entry"), ("귀가 기록", "departure"),
                ("출결", "attendance"), ("개선 요청", "suggestion")):
    try:
        print("  %-10s %s" % (이름, 하나("select count(*) from " + 표)[0]))
    except sqlite3.OperationalError:
        pass

오늘 = dt.date.today().isoformat()
print()
print("[오늘 %s]" % 오늘)
쓴사람 = 모두("select user_name, count(*) from audit_log "
              "where date(at) = ? and user_name != '' "
              "group by user_name order by 2 desc", 오늘)
if 쓴사람:
    for r in 쓴사람:
        print("  %-8s %s번 눌렀습니다" % (r[0], r[1]))
else:
    print("  아직 아무도 안 들어왔습니다")

막일 = 모두("select at, user_name, action, status from audit_log "
            "where user_name != '' order by id desc limit 8")
print()
print("[마지막으로 한 일]")
for r in 막일:
    print("  %s  %-6s %-22s %s" % (str(r[0])[:16], r[1], r[2] or "", r[3]))

print()
print("[터진 데]")
터짐 = 모두("select at, user_name, action, req_id from audit_log "
            "where status >= 500 order by id desc limit 10")
if 터짐:
    for r in 터짐:
        print("  %s  %-6s %-22s %s" % (str(r[0])[:16], r[1] or "-", r[2] or "", r[3] or ""))
else:
    print("  없습니다")

막힘 = 하나("select count(*) from audit_log where status = 429")[0]
실패 = 모두("select at, ip from audit_log where path like '/signin%' "
            "and method = 'POST' and user_name = '' order by id desc limit 5")
print()
print("[들어오려다 실패한 것]")
if 실패:
    for r in 실패:
        print("  %s  %s" % (str(r[0])[:16], r[1] or "-"))
else:
    print("  없습니다")
if 막힘:
    print("  속도 제한에 걸린 요청 %d건" % 막힘)

print()
print("[개선 요청]")
모두수 = 하나("select count(*) from suggestion")[0]
남은수 = 하나("select count(*) from suggestion where reply = ''")[0]
print("  모두 %d건 · 아직 답 안 한 것 %d건" % (모두수, 남은수))
c.close()
'''


def 어디로() -> tuple[str, str]:
    p = 뿌리 / ".nas"
    if not p.exists():
        raise SystemExit("  .nas 가 없습니다.")
    줄 = [x.strip() for x in p.read_text(encoding="utf-8").splitlines()
          if x.strip() and not x.startswith("#")]
    return 줄[0], (줄[1] if len(줄) > 1 else "9292")


def main() -> int:
    나스, 포트 = 어디로()
    바탕 = ("export PATH=$PATH:/usr/local/bin:"
            "/var/packages/ContainerManager/target/usr/bin; ")

    # 컨테이너가 살아 있는지 먼저 — 자료를 읽기 전에 알아야 할 것이다
    껍데기 = subprocess.run(
        ["ssh", "-p", 포트, "-o", "BatchMode=yes", 나스,
         바탕 + 'docker ps --filter name=majung --format "{{.Status}}"'],
        capture_output=True, text=True, encoding="utf-8", errors="replace")

    난 = subprocess.run(
        ["ssh", "-p", 포트, "-o", "BatchMode=yes", 나스,
         바탕 + "docker exec -i majung python -"],
        input=읽기, capture_output=True, text=True,
        encoding="utf-8", errors="replace")

    print()
    print("  손잡고 마중 — 지금 상황")
    print()
    print("  [서버] " + (껍데기.stdout.strip() or "안 도는 것 같습니다"))
    for 줄 in (난.stdout or "").splitlines():
        print("  " + 줄)
    if 난.returncode != 0:
        for 줄 in (난.stderr or "").splitlines():
            if 줄.strip() and "post-quantum" not in 줄 and "store now" not in 줄 \
                    and not 줄.startswith("**") and "may need to be upgraded" not in 줄:
                print("  " + 줄)
        return 1
    print()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
