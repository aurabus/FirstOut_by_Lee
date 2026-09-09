# 내 PC 에서 눌러 NAS 에 올린다.
#
#   nas-deploy.bat 을 두 번 누르면 이것이 돕니다.
#
# 하는 일은 세 가지뿐입니다.
#   1. 아직 안 올린 것이 있으면 GitHub 에 올린다
#   2. NAS 에 들어가 GitHub 에서 받아온다
#   3. NAS 에서 deploy/nas-up.sh 를 돌린다 (만들고 띄우고 살아났는지 본다)
#
# NAS 주소는 .nas 파일에 적어 둡니다 (처음 한 번만 물어봅니다).
# 이 파일은 저장소에 올라가지 않습니다.

$ErrorActionPreference = "Stop"
$root = Split-Path -Parent $PSScriptRoot
Set-Location $root

function Say($s) { Write-Host "  $s" }
function Die($s) { Write-Host ""; Write-Host "  [멈춤] $s" -ForegroundColor Red; Write-Host ""; exit 1 }

# ── NAS 주소 ──────────────────────────────────────────────
$addrFile = Join-Path $root ".nas"
if (Test-Path $addrFile) {
    $line = Get-Content $addrFile | Where-Object { $_ -and -not $_.StartsWith("#") } | Select-Object -First 1
    $NAS = $line.Trim()
} else {
    Write-Host ""
    Say "NAS 에 어떻게 들어가는지 한 번만 알려주세요."
    Say "예: aurabus@192.168.100.10   (테일스케일 주소도 됩니다)"
    Write-Host ""
    $NAS = (Read-Host "  NAS 주소").Trim()
    if (-not $NAS) { Die "주소가 비었습니다." }
    $path = Read-Host "  저장소 위치 (그냥 엔터 = /volume1/docker/majung)"
    if (-not $path) { $path = "/volume1/docker/majung" }
    @("# NAS 접속 주소와 저장소 위치. 이 파일은 저장소에 올라가지 않습니다.",
      $NAS, $path.Trim()) | Set-Content $addrFile -Encoding utf8
    Say "적어 두었습니다 (.nas)"
}
$lines = Get-Content $addrFile | Where-Object { $_ -and -not $_.StartsWith("#") }
$NAS = $lines[0].Trim()
$path = if ($lines.Count -gt 1) { $lines[1].Trim() } else { "/volume1/docker/majung" }

Write-Host ""
Say "NAS   : $NAS"
Say "저장소: $path"
Write-Host ""

# ── 1. 아직 안 올린 것이 있으면 올린다 ────────────────────────
$dirty = git status --porcelain
if ($dirty) {
    Say "아직 저장 안 한 것이 있습니다:"
    git status --short | Select-Object -First 12 | ForEach-Object { Write-Host "     $_" }
    Write-Host ""
    $answer = Read-Host "  지금 저장하고 올릴까요? (y = 예, 그 밖 = 이대로 두고 진행)"
    if ($answer -eq "y") {
        $memo = Read-Host "  무엇을 바꾸셨나요"
        if (-not $memo) { $memo = "홈페이지 손봄" }
        git add -A
        git commit -m $memo
    }
}
Say "GitHub 에 올립니다..."
git push
if ($LASTEXITCODE -ne 0) { Die "git push 에 실패했습니다." }

# ── 2·3. NAS 에서 받아 띄운다 ────────────────────────────────
Write-Host ""
Say "NAS 에서 받아 띄웁니다. 처음에는 몇 분 걸립니다..."
Write-Host ""

$cmd = "cd '$path' && git pull --ff-only && sh deploy/nas-up.sh"
ssh $NAS $cmd
if ($LASTEXITCODE -ne 0) {
    Write-Host ""
    Say "NAS 쪽에서 문제가 있었습니다. 위의 내용을 보세요."
    Say "비밀번호를 매번 묻는다면 아래 한 줄로 열쇠를 심어두시면 됩니다:"
    Say "   type `$env:USERPROFILE\.ssh\id_ed25519.pub | ssh $NAS `"cat >> .ssh/authorized_keys`""
    exit 1
}

Write-Host ""
Say "끝났습니다."
Write-Host ""
