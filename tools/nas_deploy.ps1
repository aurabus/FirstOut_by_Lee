# 내 PC 에서 눌러 NAS 에 올린다 — 처음이든 새 버전이든 이것 하나면 됩니다.
#
#   nas-deploy.bat 을 두 번 누르면 이것이 돕니다.
#
# 하는 일
#   1. 아직 안 올린 것이 있으면 GitHub 에 올린다
#   2. NAS 에 **한 번** 들어가서 (비밀번호는 그때 한 번만 치시면 됩니다)
#      받아오고 · .env 를 채우고 · 띄우고 · 살아났는지 확인한다
#
# NAS 에서 할 일은 deploy/nas-bootstrap.sh 에 적혀 있습니다. 그 파일을 통째로
# 실어 보내므로 NAS 에 미리 무엇을 갖다 둘 필요가 없습니다.
#
# 비밀번호는 이 스크립트가 만지지 않습니다. ssh 가 직접 물어보고, 어디에도
# 저장하지 않습니다.
#
# 주의 — 이 파일은 UTF-8 BOM 으로 저장해야 합니다 (PowerShell 5.1 이 cp949 로 읽습니다).

$ErrorActionPreference = "Stop"
$root = Split-Path -Parent $PSScriptRoot
Set-Location $root

function Say($s) { Write-Host "  $s" }
function Die($s) { Write-Host ""; Write-Host "  [멈춤] $s" -ForegroundColor Red; Write-Host ""; exit 1 }

$MAJUNG_REPO = "https://github.com/aurabus/FirstOut_by_Lee.git"
$SITE_REPO   = "https://github.com/aurabus/aurabus-site.git"

# ── 어디로 보낼지 ─────────────────────────────────────────
# .nas 에 적어 둡니다 (저장소에는 올라가지 않습니다). 비밀번호는 적지 않습니다.
$addrFile = Join-Path $root ".nas"
if (-not (Test-Path $addrFile)) {
    Write-Host ""
    Say "NAS 에 어떻게 들어가는지 한 번만 알려주세요. (비밀번호는 묻지 않습니다)"
    Write-Host ""
    $id = (Read-Host "  NAS 로그인 아이디").Trim()
    if (-not $id) { Die "아이디가 비었습니다." }
    $host_ = (Read-Host "  주소 (그냥 엔터 = 192.168.100.10)").Trim()
    if (-not $host_) { $host_ = "192.168.100.10" }
    $port = (Read-Host "  SSH 포트 (그냥 엔터 = 9292)").Trim()
    if (-not $port) { $port = "9292" }
    $base = (Read-Host "  놓을 자리 (그냥 엔터 = /volume1/docker)").Trim()
    if (-not $base) { $base = "/volume1/docker" }
    @("# NAS 접속 정보. 비밀번호는 여기 적지 않습니다.",
      "# 계정@주소 · SSH 포트 · 놓을 자리",
      "$id@$host_", $port, $base) | Set-Content $addrFile -Encoding utf8
    Say "적어 두었습니다 (.nas) — 다음부터는 묻지 않습니다"
}
$lines = @(Get-Content $addrFile | Where-Object { $_ -and -not $_.StartsWith("#") })
$NAS  = $lines[0].Trim()
$port = if ($lines.Count -gt 1) { $lines[1].Trim() } else { "9292" }
$base = if ($lines.Count -gt 2) { $lines[2].Trim() } else { "/volume1/docker" }

Write-Host ""
Say "NAS    : $NAS  (포트 $port)"
Say "놓을 자리: $base"

# ── 1. 아직 안 올린 것이 있으면 올린다 ────────────────────────
Write-Host ""
$dirty = git status --porcelain
if ($dirty) {
    Say "아직 저장 안 한 것이 있습니다:"
    git status --short | Select-Object -First 12 | ForEach-Object { Write-Host "     $_" }
    Write-Host ""
    $answer = Read-Host "  지금 저장하고 올릴까요? (y = 예, 그 밖 = 이대로 두고 진행)"
    if ($answer -eq "y") {
        $memo = Read-Host "  무엇을 바꾸셨나요"
        if (-not $memo) { $memo = "손봄" }
        git add -A
        git commit -m $memo
    }
}
Say "GitHub 에 올립니다..."
git push
if ($LASTEXITCODE -ne 0) { Die "git push 에 실패했습니다." }

# ── 2. NAS 에서 받아 띄운다 (연결 한 번 · 비밀번호 한 번) ──────
$sh = Join-Path $root "deploy\nas-bootstrap.sh"
if (-not (Test-Path $sh)) { Die "deploy\nas-bootstrap.sh 가 없습니다." }

# 스크립트를 통째로 실어 보낸다. 줄바꿈은 LF 로 맞춘다 — 리눅스가 CR 을 만나면
# 「bad interpreter」 같은 알 수 없는 오류를 낸다.
# UTF-8 로 못박아 읽는다. Get-Content 는 BOM 없는 파일을 cp949 로 읽어
# 한글을 깨뜨리고, 깨진 글자가 리눅스에서 문법 오류가 된다 — 한 번 겪었다.
$body = [IO.File]::ReadAllText($sh, [Text.Encoding]::UTF8) -replace "`r`n", "`n"
$b64  = [Convert]::ToBase64String([Text.Encoding]::UTF8.GetBytes($body))
$cmd  = "echo $b64 | base64 -d | sh -s '$MAJUNG_REPO' '$SITE_REPO' '$base'"

Write-Host ""
Say "──────────────────────────────────────────────"
Say "  이제 NAS 비밀번호를 한 번 치시면 됩니다."
Say "  (치는 동안 아무것도 안 보이는 게 정상입니다)"
Say "──────────────────────────────────────────────"
Write-Host ""

# -t 로 터미널을 하나 붙여 준다. 이게 없으면 NAS 쪽에서 sudo 가 비밀번호를
# 물어볼 자리가 없어 그냥 실패한다 — 시놀로지에서 도커는 sudo 로만 된다.
ssh -t -p $port -o StrictHostKeyChecking=accept-new $NAS $cmd
$code = $LASTEXITCODE

Write-Host ""
if ($code -ne 0) {
    Say "NAS 쪽에서 문제가 있었습니다. 위의 내용을 보세요."
    Write-Host ""
    Say "비밀번호를 매번 치는 게 번거로우면, 열쇠를 한 번 심어두시면 됩니다:"
    Say "   type `$env:USERPROFILE\.ssh\id_ed25519.pub | ssh -p $port $NAS `"mkdir -p ~/.ssh && cat >> ~/.ssh/authorized_keys && chmod 700 ~/.ssh && chmod 600 ~/.ssh/authorized_keys`""
    Write-Host ""
    exit 1
}

Say "끝났습니다."
Write-Host ""
Say "다음은 DSM 역방향 프록시입니다 — deploy/nas-ui.md 4장."
Write-Host ""
