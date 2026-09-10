#!/bin/sh
# NAS 에서 처음부터 끝까지 — 받아오고, 채우고, 띄우고, 살아났는지 본다.
#
# 이 파일은 NAS 에 미리 있을 필요가 없다. nas-deploy.bat 이 SSH 로 보내서 돌린다.
# 그래서 「처음 한 번」과 「그 뒤로 계속」이 같은 명령이 된다.
#
#     sh nas-bootstrap.sh <마중저장소> <홈페이지저장소> <놓을자리>
#
# 하는 일
#   1. 저장소가 없으면 받아오고, 있으면 새로 받는다
#   2. .env 가 없으면 만든다 — 세션 서명 키는 **여기서** 만들어 여기에만 둔다
#   3. 자료 폴더를 제 손으로 만든다 (도커가 만들면 주인이 root 가 된다)
#   4. 띄우고, 정말 살아났는지 두들겨 본다

set -e

MAJUNG_REPO="$1"
SITE_REPO="$2"
BASE="${3:-/volume1/docker}"

MAJUNG_DIR="$BASE/majung"
SITE_DIR="$BASE/aurabus-site"

say()  { printf '\n  %s\n' "$*"; }
step() { printf '\n── %s ─────────────────────────\n' "$*"; }
die()  { printf '\n  [멈춤] %s\n\n' "$*" >&2; exit 1; }

# ── 도커를 어떻게 부르나 ─────────────────────────────────────
find_dc() {
    if docker compose version >/dev/null 2>&1; then echo "docker compose"; return; fi
    if docker-compose version >/dev/null 2>&1; then echo "docker-compose"; return; fi
    if sudo -n docker compose version >/dev/null 2>&1; then echo "sudo docker compose"; return; fi
    if sudo -n docker-compose version >/dev/null 2>&1; then echo "sudo docker-compose"; return; fi
    echo ""
}
DC=$(find_dc)
[ -n "$DC" ] || die "도커를 찾지 못했습니다. Container Manager 를 설치해 주세요.
  (sudo 로만 되는 경우라면 비밀번호 없이 쓸 수 있게 해두셔야 합니다)"
say "도커: $DC"

# ── 받아온다 ────────────────────────────────────────────────
pull_or_clone() {
    _dir="$1"; _repo="$2"; _name="$3"
    if [ -d "$_dir/.git" ]; then
        say "$_name — 새로 받아옵니다"
        ( cd "$_dir" && git pull --ff-only )
    elif [ -n "$_repo" ]; then
        say "$_name — 처음이라 통째로 받아옵니다"
        mkdir -p "$(dirname "$_dir")"
        git clone "$_repo" "$_dir"
    else
        say "$_name — 저장소 주소가 없어 건너뜁니다"
        return 1
    fi
}

step "손잡고 마중"
pull_or_clone "$MAJUNG_DIR" "$MAJUNG_REPO" "손잡고 마중" || die "받아오지 못했습니다"
cd "$MAJUNG_DIR"

# ── .env — 없을 때만 만든다 ─────────────────────────────────
# 세션 서명 키는 이 서버에서 만들어 이 서버에만 둔다. 밖으로 나갈 일이 없으면
# 새어 나갈 일도 없다. 이미 있으면 절대 덮어쓰지 않는다 — 덮어쓰면 지금 로그인한
# 사람이 모두 튕겨 나간다.
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

# 계정 번호가 바뀌었으면 맞춰 준다 (자료 폴더 주인과 어긋나면 곧바로 죽는다)
NOW_UID=$(id -u); NOW_GID=$(id -g)
if ! grep -q "^MAJUNG_UID=$NOW_UID$" .env 2>/dev/null; then
    say "계정 번호를 지금 값으로 맞춥니다 ($NOW_UID:$NOW_GID)"
    sed -i "s/^MAJUNG_UID=.*/MAJUNG_UID=$NOW_UID/" .env
    sed -i "s/^MAJUNG_GID=.*/MAJUNG_GID=$NOW_GID/" .env
fi

# ── 자료 폴더 ───────────────────────────────────────────────
# 없으면 도커가 대신 만드는데 그때 주인이 root 가 되어, 자료를 못 쓰고 계속 죽는다
[ -d data ] || { say "자료 폴더를 만듭니다 (data/)"; mkdir -p data; }

step "손잡고 마중 — 만들고 띄웁니다 (처음에는 몇 분)"
$DC up -d --build

step "아우라버스 홈페이지"
if pull_or_clone "$SITE_DIR" "$SITE_REPO" "홈페이지"; then
    cd "$SITE_DIR"
    $DC up -d
else
    say "홈페이지는 건너뛰었습니다"
fi

# ── 살아났는지 본다 ─────────────────────────────────────────
step "일어나기를 기다립니다"
i=0
while [ $i -lt 45 ]; do
    if curl -fsS http://127.0.0.1:8765/health >/dev/null 2>&1; then break; fi
    i=$((i + 1)); sleep 2
done

printf '\n'
BAD=0
if curl -fsS http://127.0.0.1:8765/health >/dev/null 2>&1; then
    say "○ 손잡고 마중  http://127.0.0.1:8765/   살아 있습니다"
else
    say "✗ 손잡고 마중이 응답하지 않습니다"
    ( cd "$MAJUNG_DIR" && $DC logs --tail=25 majung ) || true
    BAD=1
fi

if [ -d "$SITE_DIR" ]; then
    if curl -fsS -o /dev/null http://127.0.0.1:8080/ 2>/dev/null; then
        say "○ 홈페이지      http://127.0.0.1:8080/   살아 있습니다"
    else
        say "✗ 홈페이지가 응답하지 않습니다"
        ( cd "$SITE_DIR" && $DC logs --tail=25 ) || true
        BAD=1
    fi
fi

printf '\n'
[ $BAD -eq 0 ] || die "위의 로그를 보고 고쳐주세요."
say "다 됐습니다."
printf '\n'
