# 내 PC 에서 손잡고 마중을 띄워 본다 — NAS 에 올리기 전에.
#
#   local-test.bat 을 두 번 누르면 이것이 돕니다.
#
# NAS 의 deploy/nas-up.sh 와 하는 일이 같습니다. 준비가 됐는지 보고, 만들고,
# 띄우고, 정말 살아났는지 두들겨 확인합니다.

$ErrorActionPreference = "Stop"
$뿌리 = Split-Path -Parent $PSScriptRoot
Set-Location $뿌리

function 말($s) { Write-Host "  $s" }
function 탈($s) { Write-Host ""; Write-Host "  [멈춤] $s" -ForegroundColor Red; Write-Host ""; exit 1 }

Write-Host ""

# ── 도커가 있는가 ────────────────────────────────────────────
if (-not (Get-Command docker -ErrorAction SilentlyContinue)) {
    탈 "도커를 찾지 못했습니다. Docker Desktop 을 설치하고 한 번 실행해 주세요."
}
docker info 2>&1 | Out-Null
if ($LASTEXITCODE -ne 0) {
    탈 "Docker Desktop 이 아직 준비되지 않았습니다. 트레이의 고래 아이콘이 멈출 때까지 기다렸다 다시 눌러주세요."
}
말 "도커: $((docker version --format '{{.Server.Version}}' 2>$null))"

# ── 비밀 값 ─────────────────────────────────────────────────
if (-not (Test-Path ".env")) {
    탈 ".env 파일이 없습니다.  copy .env.example .env  로 만들고 MAJUNG_SECRET 을 채워주세요."
}
$키 = (Select-String -Path ".env" -Pattern "^MAJUNG_SECRET=(.+)$").Matches.Groups[1].Value
if (-not $키) { 탈 ".env 의 MAJUNG_SECRET 이 비어 있습니다." }

# ── 자료 폴더 ───────────────────────────────────────────────
if (-not (Test-Path "data")) { New-Item -ItemType Directory data | Out-Null; 말 "자료 폴더를 만들었습니다 (data/)" }

# ── 만들고 띄운다 ───────────────────────────────────────────
Write-Host ""
말 "만들고 띄웁니다. 처음에는 몇 분 걸립니다..."
Write-Host ""
docker compose -f docker-compose.yml -f docker-compose.local.yml up -d --build
if ($LASTEXITCODE -ne 0) { 탈 "띄우지 못했습니다. 위의 내용을 보세요." }

# ── 살아났는지 본다 ─────────────────────────────────────────
Write-Host ""
말 "일어나기를 기다립니다..."
$살았나 = $false
foreach ($i in 1..40) {
    try {
        $r = Invoke-WebRequest "http://127.0.0.1:8765/health" -TimeoutSec 3 -UseBasicParsing
        if ($r.StatusCode -eq 200) { $살았나 = $true; break }
    } catch { Start-Sleep -Milliseconds 1500 }
}

Write-Host ""
if (-not $살았나) {
    말 "[문제] 응답이 없습니다. 까닭을 봅니다:"
    Write-Host ""
    docker compose logs --tail=30 majung
    Write-Host ""
    탈 "위 로그를 보고 고쳐주세요."
}

# ── 몇 가지 더 확인한다 ─────────────────────────────────────
말 "살아 있습니다. 몇 가지 더 봅니다."
Write-Host ""

$화면 = Invoke-WebRequest "http://127.0.0.1:8765/signin" -TimeoutSec 5 -UseBasicParsing
if ($화면.Content -match "손잡고") { 말 "○ 로그인 화면이 그려집니다" }
else { 말 "✗ 화면이 이상합니다 — 글꼴·CSS 가 꾸러미에 안 담겼을 수 있습니다" }

$css = Invoke-WebRequest "http://127.0.0.1:8765/static/aurabus.css" -TimeoutSec 5 -UseBasicParsing
if ($css.StatusCode -eq 200) { 말 "○ 화면 결(CSS)이 내려옵니다" }

$시각 = (docker compose exec -T majung date "+%Y-%m-%d %H:%M %Z") -join ""
말 "○ 컨테이너 시각: $시각   ← KST 여야 합니다"

Write-Host ""
말 "──────────────────────────────────────────"
말 "  http://127.0.0.1:8765/   에서 열어보세요"
말 "──────────────────────────────────────────"
Write-Host ""
말 "로그인해 보시려면 운영자 계정을 한 번 만드세요:"
말 "   docker compose exec majung firstout --operator 아이디:비밀번호 --host 127.0.0.1"
말 "   (계정 생성 글이 뜨면 Ctrl+C)"
Write-Host ""
말 "끝낼 때:  docker compose down"
Write-Host ""
