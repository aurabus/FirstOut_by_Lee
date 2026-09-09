# Container Manager 에 손으로 올릴 이미지 파일(.tar)을 만든다.
#
#   make-image.bat 을 두 번 누르면 이것이 돕니다.
#
# 왜 그냥 build 가 아닌가 — 요즘 도커는 이미지에 「증명서」(provenance·SBOM)를
# 함께 붙여 여러 겹으로 만든다. 그러면 NAS 의 오래된 도커가 그 파일을 못 읽는다.
# 여기서는 그것을 끄고 **한 겹짜리 리눅스 amd64 이미지**로 만든다.
#
# 주의 — 이 파일은 UTF-8 BOM 으로 저장해야 합니다 (PowerShell 5.1 이 cp949 로 읽습니다).

$ErrorActionPreference = "Stop"
$root = Split-Path -Parent $PSScriptRoot
Set-Location $root

function Say($s) { Write-Host "  $s" }
function Die($s) { Write-Host ""; Write-Host "  [멈춤] $s" -ForegroundColor Red; Write-Host ""; exit 1 }

Write-Host ""
if (-not (Get-Command docker -ErrorAction SilentlyContinue)) {
    Die "도커를 찾지 못했습니다. Docker Desktop 을 켜 주세요."
}
docker info 2>&1 | Out-Null
if ($LASTEXITCODE -ne 0) { Die "Docker Desktop 이 아직 준비되지 않았습니다." }

$out = Join-Path $root "dist"
if (-not (Test-Path $out)) { New-Item -ItemType Directory $out | Out-Null }
$tar = Join-Path $out "majung.tar"

Say "이미지를 만듭니다 (한 겹 · linux/amd64)..."
Write-Host ""
docker build --platform linux/amd64 --provenance=false --sbom=false -t majung:latest .
if ($LASTEXITCODE -ne 0) { Die "만들지 못했습니다. 위의 내용을 보세요." }

Write-Host ""
Say "제대로 도는지 한 번 띄워 봅니다..."
docker rm -f majung-imgcheck 2>&1 | Out-Null
docker run -d --name majung-imgcheck -e MAJUNG_SECRET=check-only-not-a-real-secret-1234567890 -p 18765:8000 majung:latest | Out-Null
$ok = $false
foreach ($i in 1..40) {
    try {
        if ((Invoke-WebRequest "http://127.0.0.1:18765/health" -TimeoutSec 3 -UseBasicParsing).StatusCode -eq 200) { $ok = $true; break }
    } catch { Start-Sleep -Milliseconds 1500 }
}
if ($ok) {
    $page = Invoke-WebRequest "http://127.0.0.1:18765/signin" -TimeoutSec 5 -UseBasicParsing
    if ($page.Content -match "손잡고") { Say "○ 로그인 화면이 그려집니다" } else { Say "✗ 화면이 이상합니다" }
    Say ("○ 컨테이너 시각: " + ((docker exec majung-imgcheck date "+%Y-%m-%d %H:%M %Z") -join ""))
} else {
    docker logs majung-imgcheck
    docker rm -f majung-imgcheck | Out-Null
    Die "만든 이미지가 뜨지 않습니다."
}
docker rm -f majung-imgcheck | Out-Null

Write-Host ""
Say "파일로 내보냅니다..."
if (Test-Path $tar) { Remove-Item $tar }
docker save -o $tar majung:latest
if ($LASTEXITCODE -ne 0) { Die "내보내지 못했습니다." }

$mb = [math]::Round((Get-Item $tar).Length / 1MB)
Write-Host ""
Say "──────────────────────────────────────────────"
Say "  다 됐습니다.  $tar"
Say "  크기: $mb MB"
Say "──────────────────────────────────────────────"
Write-Host ""
Say "Container Manager → 이미지 → 추가 → 파일에서 추가 → 이 파일을 고르세요."
Write-Host ""
