# 여기서 만든 것을 NAS 로 보내 돌린다.
#
#   nas-deploy.bat 을 두 번 누르면 이것이 돕니다.
#
# 하는 일
#   1. 여기서 이미지를 만든다
#   2. 여기서 한 번 띄워 확인한다 (안 되면 NAS 로 보내지 않는다)
#   3. 이미지와 설정을 한 묶음으로 NAS 에 보낸다
#   4. NAS 에서 들이고 띄우고, 살아났는지 확인한다
#
# **NAS 에는 도커 말고 아무것도 필요 없습니다.** git 도, 소스도, 만드는 과정도.
#
# 홈페이지는 여기서 다루지 않습니다 — 제 저장소(Aurabus Site)에서 제 손으로
# 배포됩니다. 한 배포가 다른 쪽을 흔들지 않게 갈라 두었습니다.
# 여기서 시험한 그 이미지가 글자 하나 다르지 않게 NAS 에서 돕니다.
#
# 비밀번호는 이 스크립트가 만지지 않습니다. ssh 가 직접 물어보고,
# 어디에도 저장하지 않습니다. 연결은 한 번뿐이라 한 번만 치시면 됩니다.
#
# 주의 — 이 파일은 UTF-8 BOM 으로 저장해야 합니다 (PowerShell 5.1 이 cp949 로 읽습니다).

$ErrorActionPreference = "Stop"
$root = Split-Path -Parent $PSScriptRoot
Set-Location $root

function Say($s) { Write-Host "  $s" }
function Step($s) { Write-Host ""; Write-Host "── $s ─────────────────────────" -ForegroundColor Cyan }
function Die($s) { Write-Host ""; Write-Host "  [멈춤] $s" -ForegroundColor Red; Write-Host ""; exit 1 }

# ── 어디로 보낼지 ─────────────────────────────────────────
$addrFile = Join-Path $root ".nas"
if (-not (Test-Path $addrFile)) {
    Write-Host ""
    Say "NAS 에 어떻게 들어가는지 한 번만 알려주세요. (비밀번호는 묻지 않습니다)"
    Write-Host ""
    $id = (Read-Host "  NAS 로그인 아이디").Trim()
    if (-not $id) { Die "아이디가 비었습니다." }
    $h = (Read-Host "  주소 (그냥 엔터 = 192.168.100.10)").Trim()
    if (-not $h) { $h = "192.168.100.10" }
    $p = (Read-Host "  SSH 포트 (그냥 엔터 = 9292)").Trim()
    if (-not $p) { $p = "9292" }
    $b = (Read-Host "  놓을 자리 (그냥 엔터 = /volume1/docker/aurabus)").Trim()
    if (-not $b) { $b = "/volume1/docker/aurabus" }
    @("# NAS 접속 정보. 비밀번호는 여기 적지 않습니다.",
      "# 계정@주소 · SSH 포트 · 놓을 자리",
      "$id@$h", $p, $b) | Set-Content $addrFile -Encoding utf8
    Say "적어 두었습니다 (.nas)"
}
$lines = @(Get-Content $addrFile | Where-Object { $_ -and -not $_.StartsWith("#") })
$NAS  = $lines[0].Trim()
$port = if ($lines.Count -gt 1) { $lines[1].Trim() } else { "9292" }
$base = if ($lines.Count -gt 2) { $lines[2].Trim() } else { "/volume1/docker/aurabus" }

Write-Host ""
Say "NAS    : $NAS  (포트 $port)"
Say "놓을 자리: $base"

# ── 1. 여기서 만든다 ──────────────────────────────────────
Step "이미지를 만듭니다"
if (-not (Get-Command docker -ErrorAction SilentlyContinue)) { Die "Docker Desktop 을 켜 주세요." }
docker info 2>&1 | Out-Null
if ($LASTEXITCODE -ne 0) { Die "Docker Desktop 이 아직 준비되지 않았습니다." }

# 한 겹짜리 linux/amd64 로 만든다 — 여러 겹이면 NAS 의 도커가 못 읽는다
docker build --platform linux/amd64 --provenance=false --sbom=false -t majung:latest .
if ($LASTEXITCODE -ne 0) { Die "만들지 못했습니다." }

# ── 2. 보내기 전에 여기서 확인한다 ─────────────────────────
Step "보내기 전에 여기서 띄워 봅니다"
docker rm -f majung-precheck 2>&1 | Out-Null
docker run -d --name majung-precheck -e MAJUNG_SECRET=precheck-only-not-a-real-secret-123456 -p 18765:8000 majung:latest | Out-Null
$ok = $false
foreach ($i in 1..40) {
    try { if ((Invoke-WebRequest "http://127.0.0.1:18765/health" -TimeoutSec 3 -UseBasicParsing).StatusCode -eq 200) { $ok = $true; break } }
    catch { Start-Sleep -Milliseconds 1500 }
}
if (-not $ok) {
    docker logs majung-precheck
    docker rm -f majung-precheck | Out-Null
    Die "여기서도 안 뜹니다. NAS 로 보내지 않았습니다."
}
$page = Invoke-WebRequest "http://127.0.0.1:18765/signin" -TimeoutSec 5 -UseBasicParsing
if ($page.Content -match "손잡고") { Say "○ 로그인 화면이 그려집니다" } else { Say "✗ 화면이 이상합니다" }
Say ("○ 시각: " + ((docker exec majung-precheck date "+%Y-%m-%d %H:%M %Z") -join ""))
docker rm -f majung-precheck | Out-Null

# ── 3. 보낼 짐을 싼다 ─────────────────────────────────────
Step "보낼 짐을 쌉니다"
$pack = Join-Path $env:TEMP "aurabus-pack"
if (Test-Path $pack) { Remove-Item $pack -Recurse -Force }
New-Item -ItemType Directory $pack | Out-Null

docker save -o (Join-Path $pack "majung.tar") majung:latest
if ($LASTEXITCODE -ne 0) { Die "이미지를 파일로 내보내지 못했습니다." }
Copy-Item (Join-Path $root "deploy\compose.nas.yml") $pack
Copy-Item (Join-Path $root "deploy\nas-run.sh") $pack

# 리눅스에서 읽을 것이므로 줄바꿈을 LF 로 맞춘다
$sh = Join-Path $pack "nas-run.sh"
[IO.File]::WriteAllText($sh, ([IO.File]::ReadAllText($sh, [Text.Encoding]::UTF8) -replace "`r`n", "`n"), (New-Object Text.UTF8Encoding($false)))

$mb = [math]::Round(((Get-ChildItem $pack -Recurse -File | Measure-Object Length -Sum).Sum / 1MB))
Say "짐 크기: $mb MB"

# ── 4. 보내고 돌린다 (연결 한 번 · 비밀번호 한 번) ──────────
Write-Host ""
Say "──────────────────────────────────────────────"
Say "  이제 NAS 비밀번호를 한 번 치시면 됩니다."
Say "  (치는 동안 아무것도 안 보이는 게 정상입니다)"
Say "──────────────────────────────────────────────"
Write-Host ""

# PowerShell 은 파이프로 흐르는 바이트를 망가뜨린다. 그래서 cmd 에게 맡긴다.
$remote = "rm -rf /tmp/aurabus-pack && mkdir -p /tmp/aurabus-pack && tar -xf - -C /tmp/aurabus-pack && sh /tmp/aurabus-pack/nas-run.sh '$base'"
$line = "tar -cf - -C `"$pack`" . | ssh -p $port -o StrictHostKeyChecking=accept-new $NAS `"$remote`""
cmd /c $line
$code = $LASTEXITCODE

Remove-Item $pack -Recurse -Force -ErrorAction SilentlyContinue

Write-Host ""
if ($code -ne 0) {
    Say "NAS 쪽에서 문제가 있었습니다. 위의 내용을 보세요."
    Write-Host ""
    exit 1
}
Say "끝났습니다."
Write-Host ""
Say "다음은 DSM 역방향 프록시입니다 — deploy/nas-ui.md 4장."
Write-Host ""
