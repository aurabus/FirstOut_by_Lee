"""선생님들이 보내신 개선 요청을 읽어 온다.

화면마다 「개선 요청」 단추가 있다. 불편한 순간에 그 자리에서 보내시는 것이라
**어느 화면에서 보냈는지**가 함께 담긴다. 「명단이 불편해요」와 「1차 차량
명단에서 불편해요」는 다른 이야기이기 때문이다.

    python tools/suggestions.py           아직 답 안 한 것만
    python tools/suggestions.py --전부    답한 것까지 모두

읽기만 한다. 답은 운영자가 화면에서 단다 — 여기서는 아무것도 고치지 않는다.
"""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

뿌리 = Path(__file__).resolve().parent.parent

# 서버에서 돌릴 짧은 글. 파일로 보내지 않고 표준입력으로 흘려 넣는다 —
# 서버에 우리 흔적을 남기지 않으려고.
읽기 = '''
import sqlite3, sys
sys.stdout.reconfigure(encoding="utf-8", errors="replace")
전부 = len(sys.argv) > 1 and sys.argv[1] == "all"
c = sqlite3.connect("file:/data/majung.db?mode=ro", uri=True)
줄 = ("select id, created_at, kinder_name, user_name, where_, status, body, "
      "reply, replied_at from ("
      "select id, created_at, kinder_name, user_name, \\"where\\" as where_, "
      "status, body, reply, replied_at from suggestion) order by id")
for r in c.execute(줄):
    번호, 때, 원, 누구, 어디, 상태, 몸, 답, 답한때 = r
    if not 전부 and 답:
        continue
    print("=== #%s  %s" % (번호, str(때)[:19]))
    print("    보낸 분: %s · %s" % (누구 or "?", 원 or "?"))
    print("    화면    : %s" % (어디 or "?"))
    print("    상태    : %s" % (상태 or "?"))
    print("    내용    : %s" % (몸 or "").replace("\\n", "\\n              "))
    if 답:
        print("    답      : %s" % 답.replace("\\n", "\\n              "))
        print("    답한 때 : %s" % str(답한때)[:19])
    print()
남 = c.execute("select count(*) from suggestion where reply = ''").fetchone()[0]
모두 = c.execute("select count(*) from suggestion").fetchone()[0]
print("모두 %d건 · 아직 답 안 한 것 %d건" % (모두, 남))
'''


def 어디로() -> tuple[str, str]:
    """.nas 에 적어 둔 접속 정보."""
    p = 뿌리 / ".nas"
    if not p.exists():
        raise SystemExit("  .nas 가 없습니다. tools/nas_deploy.ps1 을 한 번 돌려주세요.")
    줄 = [x.strip() for x in p.read_text(encoding="utf-8").splitlines()
          if x.strip() and not x.startswith("#")]
    return 줄[0], (줄[1] if len(줄) > 1 else "9292")


def main() -> int:
    전부 = "--전부" in sys.argv or "--all" in sys.argv
    나스, 포트 = 어디로()

    안 = "export PATH=$PATH:/usr/local/bin:/var/packages/ContainerManager/target/usr/bin; "
    안 += "docker exec -i majung python - " + ("all" if 전부 else "")
    난 = subprocess.run(
        ["ssh", "-p", 포트, "-o", "BatchMode=yes", 나스, 안],
        input=읽기, capture_output=True, text=True,
        encoding="utf-8", errors="replace")

    print()
    print("  개선 요청" + ("" if 전부 else " — 아직 답 안 한 것만"))
    print()
    글 = 난.stdout.strip()
    if 글:
        for 한줄 in 글.splitlines():
            print("  " + 한줄)
    if 난.returncode != 0:
        찌꺼기 = [x for x in 난.stderr.splitlines()
                if x.strip() and "post-quantum" not in x and not x.startswith("**")
                and "store now" not in x and "may need to be upgraded" not in x]
        for 한줄 in 찌꺼기:
            print("  " + 한줄)
        return 1
    print()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
