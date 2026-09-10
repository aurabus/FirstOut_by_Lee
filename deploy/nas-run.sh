#!/bin/sh
# NAS 에서 받은 것을 풀어 돌린다.
#
# nas-deploy.bat 이 이미지와 compose 를 한 묶음으로 보내면서
# 이 스크립트를 함께 보낸다. NAS 에는 **도커 말고 아무것도 필요 없다** —
# git 도, 소스도, 만드는 과정도.
#
#     sh nas-run.sh <놓을자리>

set -e

BASE="${1:-/volume1/docker/aurabus}"
HERE=$(cd "$(dirname "$0")" && pwd)

say()  { printf '\n  %s\n' "$*"; }
step() { printf '\n── %s ─────────────────────────\n' "$*"; }
die()  { printf '\n  [멈춤] %s\n\n' "$*" >&2; exit 1; }

# ── 도커를 어떻게 부르나 ─────────────────────────────────────
# 시놀로지는 SSH 로 들어오면 PATH 가 짧아 docker 가 안 잡힌다.
PATH="$PATH:/usr/local/bin:/usr/bin:/bin:/sbin:/usr/sbin"
export PATH

DOCKER=""
for c in docker /usr/local/bin/docker \
         /var/packages/ContainerManager/target/usr/bin/docker \
         /var/packages/Docker/target/usr/bin/docker
do
    if command -v "$c" >/dev/null 2>&1 || [ -x "$c" ]; then DOCKER="$c"; break; fi
done
[ -n "$DOCKER" ] || die "도커를 찾지 못했습니다. Container Manager 를 확인해 주세요."

if $DOCKER info >/dev/null 2>&1; then
    SUDO=""
elif sudo -n $DOCKER info >/dev/null 2>&1; then
    SUDO="sudo"
else
    die "도커에 말을 걸지 못했습니다.
  $(id -un) 을 DSM 제어판 → 사용자 및 그룹 → 그룹 에서 administrators 에 넣거나,
  Container Manager 가 실행 중인지 확인해 주세요."
fi

if $SUDO $DOCKER compose version >/dev/null 2>&1; then
    DC="$SUDO $DOCKER compose"
elif command -v docker-compose >/dev/null 2>&1; then
    DC="$SUDO docker-compose"
else
    die "docker compose 를 찾지 못했습니다."
fi
say "도커: $DC"

mkdir -p "$BASE"

# ── 이미지를 들인다 ─────────────────────────────────────────
step "보내온 이미지를 들입니다"
[ -f "$HERE/majung.tar" ] || die "majung.tar 이 안 왔습니다."
$SUDO $DOCKER load -i "$HERE/majung.tar"

# ── 설정 ────────────────────────────────────────────────────
cp "$HERE/compose.nas.yml" "$BASE/docker-compose.yml"

# 자료 폴더 — 없으면 도커가 만들면서 주인이 root 가 되어 곧바로 죽는다
[ -d "$BASE/data" ] || { say "자료 폴더를 만듭니다"; mkdir -p "$BASE/data"; }

# .env — 없을 때만 만든다.
# 세션 서명 키는 **이 서버에서 만들어 이 서버에만** 둔다. 이미 있으면 절대
# 덮어쓰지 않는다 — 덮어쓰면 지금 로그인해 있는 사람이 모두 튕겨 나간다.
cd "$BASE"
if [ -f .env ]; then
    say ".env 는 이미 있습니다 (그대로 둡니다)"
else
    say ".env 를 만듭니다 — 서명 키는 여기서 만들어 여기에만 둡니다"
    KEY=$(LC_ALL=C tr -dc 'A-Za-z0-9_-' < /dev/urandom | head -c 64)
    [ -n "$KEY" ] || die "서명 키를 만들지 못했습니다"
    {
        echo "# 이 서버에서 만들어진 값입니다. 밖으로 옮기지 마세요."
        echo "MAJUNG_SECRET=$KEY"
        echo "MAJUNG_PUBLIC_URL=https://majung.aurabus.com"
        echo "MAJUNG_PROXY_HOPS=1"
        echo "MAJUNG_SKIN="
        echo "MAJUNG_UID=$(id -u)"
        echo "MAJUNG_GID=$(id -g)"
    } > .env
fi
chmod 600 .env 2>/dev/null || true

# 시놀로지 ACL 을 넘기 위한 그룹.
# 공유 폴더의 ACL 은 소유자 번호가 아니라 administrators 그룹에 쓰기를 준다.
# 내가 그 그룹에 들어 있으면 컨테이너에도 달아 준다 — 내가 가진 것 이상은 주지 않는다.
ADMIN_GID=$(awk -F: '$1=="administrators"{print $3}' /etc/group 2>/dev/null | head -1)
case " $(id -G) " in
    *" $ADMIN_GID "*) : ;;
    *) ADMIN_GID=$(id -g) ;;
esac
[ -n "$ADMIN_GID" ] || ADMIN_GID=$(id -g)
if grep -q "^MAJUNG_EXTRA_GID=" .env 2>/dev/null; then
    sed -i "s/^MAJUNG_EXTRA_GID=.*/MAJUNG_EXTRA_GID=$ADMIN_GID/" .env
else
    echo "MAJUNG_EXTRA_GID=$ADMIN_GID" >> .env
fi

# 계정 번호가 바뀌었으면 맞춰 준다 (자료 폴더 주인과 어긋나면 곧바로 죽는다)
NOW_UID=$(id -u); NOW_GID=$(id -g)
if ! grep -q "^MAJUNG_UID=$NOW_UID$" .env 2>/dev/null; then
    say "계정 번호를 지금 값으로 맞춥니다 ($NOW_UID:$NOW_GID)"
    sed -i "s/^MAJUNG_UID=.*/MAJUNG_UID=$NOW_UID/" .env
    sed -i "s/^MAJUNG_GID=.*/MAJUNG_GID=$NOW_GID/" .env
fi

# ── 정말 쓸 수 있는지 미리 본다 ─────────────────────────────
# 여기서 막히면 서버는 파이썬 오류 스무 줄을 뱉고 죽는다. 무슨 일인지 알아보기
# 어려우니, 그 전에 한 번 써 보고 사람 말로 멈춘다.
step "자료 폴더에 쓸 수 있는지 봅니다"
if $SUDO $DOCKER run --rm -u "$(id -u):$(id -g)" --group-add "$ADMIN_GID"         -v "$BASE/data:/data" majung:latest         sh -c 'touch /data/.write-test && rm -f /data/.write-test' 2>/dev/null; then
    say "○ 쓸 수 있습니다"
else
    die "자료 폴더에 쓰지 못합니다: $BASE/data
  DSM File Station 에서 그 폴더를 오른쪽 클릭 → 속성 → 권한 으로 가서
  **Everyone** 에게 읽기·쓰기를 주시면 열립니다.
  (지금 번호: $(id -u):$(id -g), 더한 그룹: $ADMIN_GID)"
fi

# ── 띄운다 ──────────────────────────────────────────────────
step "띄웁니다"
$DC up -d

# ── 살아났는지 본다 ─────────────────────────────────────────
step "일어나기를 기다립니다"
i=0
while [ $i -lt 40 ]; do
    if curl -fsS http://127.0.0.1:8765/health >/dev/null 2>&1; then break; fi
    i=$((i + 1)); sleep 2
done

printf '\n'
BAD=0
if curl -fsS http://127.0.0.1:8765/health >/dev/null 2>&1; then
    say "○ 손잡고 마중  http://127.0.0.1:8765/   살아 있습니다"
else
    say "✗ 손잡고 마중이 응답하지 않습니다"
    $DC logs --tail=25 majung || true
    BAD=1
fi

# 보내온 짐은 치운다 — 이미지 파일이 그대로 쌓이면 디스크만 먹는다
rm -rf "$HERE" 2>/dev/null || true

printf '\n'
[ $BAD -eq 0 ] || die "위의 로그를 보고 고쳐주세요."
say "다 됐습니다.  놓인 자리: $BASE"
printf '\n'
