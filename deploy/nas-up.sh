#!/bin/sh
# NAS 에서 홈페이지와 손잡고 마중을 띄운다. 처음 올릴 때도, 새 버전을 올릴 때도 이것 하나면 된다.
#
#     cd /volume1/docker/majung/app
#     sh deploy/nas-up.sh
#
# 하는 일: 준비가 됐는지 확인 → 자료 폴더 챙기기 → 만들기 → 띄우기 → 살아났는지 보기.
# 빠뜨리기 쉬운 것(자료 폴더의 주인, .env 의 비밀 값)을 먼저 잡아준다.

set -e
cd "$(dirname "$0")/.."

말() { printf '\n  %s\n' "$*"; }
탈() { printf '\n  [멈춤] %s\n\n' "$*" >&2; exit 1; }

# ── 도커를 어떻게 부르는지 알아낸다 ──────────────────────────
# DSM 판에 따라 docker compose 이기도 하고 docker-compose 이기도 하다.
# 그리고 sudo 가 있어야 하는 경우가 많다.
찾기() {
    if docker compose version >/dev/null 2>&1; then echo "docker compose"; return; fi
    if docker-compose version >/dev/null 2>&1; then echo "docker-compose"; return; fi
    if sudo -n docker compose version >/dev/null 2>&1; then echo "sudo docker compose"; return; fi
    if sudo -n docker-compose version >/dev/null 2>&1; then echo "sudo docker-compose"; return; fi
    if sudo docker compose version >/dev/null 2>&1; then echo "sudo docker compose"; return; fi
    if sudo docker-compose version >/dev/null 2>&1; then echo "sudo docker-compose"; return; fi
    echo ""
}
DC=$(찾기)
[ -n "$DC" ] || 탈 "도커를 찾지 못했습니다. 패키지 센터에서 Container Manager 를 설치해 주세요."
말 "도커: $DC"

# ── 비밀 값이 채워져 있는가 ─────────────────────────────────
[ -f .env ] || 탈 ".env 파일이 없습니다.  cp .env.example .env  로 만들고 값을 채워주세요."
. ./.env 2>/dev/null || true
[ -n "$MAJUNG_SECRET" ] || 탈 ".env 의 MAJUNG_SECRET 이 비어 있습니다. 세션 서명 키를 넣어주세요."
chmod 600 .env 2>/dev/null || true

# ── 자료 폴더 ──────────────────────────────────────────────
# 없으면 도커가 대신 만드는데 그때 주인이 root 가 되어 손잡고 마중이 죽는다.
if [ ! -d data ]; then
    말 "자료 폴더를 만듭니다 (data/)"
    mkdir -p data
fi
내UID=$(id -u); 내GID=$(id -g)
if [ "${MAJUNG_UID:-1000}" != "$내UID" ] || [ "${MAJUNG_GID:-1000}" != "$내GID" ]; then
    말 "[알림] .env 의 번호가 지금 계정과 다릅니다 — MAJUNG_UID=$내UID MAJUNG_GID=$내GID 이어야 맞습니다."
    말 "        이대로 두면 자료를 쓰지 못할 수 있습니다."
fi

# ── 홈페이지가 들어와 있는가 ────────────────────────────────
if [ ! -f site/main.html ] && [ ! -f site/index.html ]; then
    말 "[알림] site/ 에 홈페이지 파일이 없습니다. 손잡고 마중만 뜹니다."
fi

# ── 만들고 띄운다 ──────────────────────────────────────────
말 "만들고 띄웁니다. 처음에는 몇 분 걸립니다..."
$DC up -d --build

# ── 살아났는지 본다 ────────────────────────────────────────
말 "일어나기를 기다립니다..."
i=0
while [ $i -lt 60 ]; do
    if curl -fsS http://127.0.0.1:8765/health >/dev/null 2>&1; then break; fi
    i=$((i + 1)); sleep 2
done

printf '\n  ── 지금 상태 ──\n\n'
$DC ps

printf '\n'
if curl -fsS http://127.0.0.1:8765/health >/dev/null 2>&1; then
    말 "손잡고 마중  http://127.0.0.1:8765/   살아 있습니다"
else
    말 "[문제] 손잡고 마중이 응답하지 않습니다.  $DC logs --tail=50 majung  으로 까닭을 보세요."
fi
if curl -fsS -o /dev/null http://127.0.0.1:8080/ 2>/dev/null; then
    말 "홈페이지     http://127.0.0.1:8080/   살아 있습니다"
else
    말 "[문제] 홈페이지가 응답하지 않습니다.  $DC logs --tail=50 site  으로 까닭을 보세요."
fi

printf '\n  다음: DSM 역방향 프록시가 이 둘을 밖으로 이어줍니다 (deploy/README.md 6~7장)\n\n'
