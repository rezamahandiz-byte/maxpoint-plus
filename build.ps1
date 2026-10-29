# build.ps1 — MAXPOINT-Plus v0.7 one-command APK builder
#
# Usage:
#   powershell -ExecutionPolicy Bypass -File .\build.ps1
#
# What it does (in order, no interactive prompts except initial gh login):
#   1. Verify pyproject.toml + src/main.py exist
#   2. Ensure git + gh CLI are installed (winget if missing)
#   3. Ensure gh is logged in (gh auth login --web if not)
#   4. git add . + commit if there are changes
#   5. git push -u origin main --force
#   6. gh workflow run "Build MAXPOINT-Plus APK"
#   7. gh run watch --exit-status
#   8. gh run download to $env:USERPROFILE\Downloads\maxpoint-plus-build
#   9. Print the APK path (arm64-v8a recommended)
#
# On failure: prints the failed run logs and exits 1.

$ErrorActionPreference = 'Stop'
[Console]::OutputEncoding = [System.Text.Encoding]::UTF8

$RepoName = 'maxpoint-plus'
$WorkflowName = 'Build MAXPOINT-Plus APK'
$OutDir = Join-Path $env:USERPROFILE 'Downloads\maxpoint-plus-build'

function Write-Step($msg) { Write-Host "`n=== $msg ===" -ForegroundColor Cyan }
function Write-OK($msg)   { Write-Host "  OK: $msg" -ForegroundColor Green }
function Write-Err($msg)  { Write-Host "  ERROR: $msg" -ForegroundColor Red }
function Write-Fa($msg)   { Write-Host "  $msg" -ForegroundColor Yellow }

# ────────────────────────────────────────────────────────────────────────────
# 1. Verify project files
# ────────────────────────────────────────────────────────────────────────────
Write-Step 'بررسی فایل‌های پروژه'
if (-not (Test-Path 'pyproject.toml')) { Write-Err 'pyproject.toml پیدا نشد'; exit 1 }
if (-not (Test-Path 'src\main.py'))    { Write-Err 'src\main.py پیدا نشد'; exit 1 }
Write-OK 'فایل‌های پروژه موجودند'

# ────────────────────────────────────────────────────────────────────────────
# 2. Ensure git + gh are installed
# ────────────────────────────────────────────────────────────────────────────
Write-Step 'بررسی نصب git و gh'

function Ensure-Tool($tool, $wingetId) {
    $cmd = Get-Command $tool -ErrorAction SilentlyContinue
    if ($cmd) { Write-OK "$tool نصب است"; return $true }
    Write-Fa "$tool نصب نیست — با winget نصب می‌کنیم..."
    winget install --id $wingetId -e --accept-source-agreements --accept-package-agreements
    # Refresh PATH for this session
    $env:Path = [System.Environment]::GetEnvironmentVariable('Path','Machine') + ';' + [System.Environment]::GetEnvironmentVariable('Path','User')
    $cmd = Get-Command $tool -ErrorAction SilentlyContinue
    if ($cmd) { Write-OK "$tool نصب شد"; return $true }
    Write-Err "$tool نصب نشد — دستی نصبش کن"; return $false
}

if (-not (Ensure-Tool 'git' 'Git.Git')) { exit 1 }
if (-not (Ensure-Tool 'gh'  'GitHub.cli')) { exit 1 }

# ────────────────────────────────────────────────────────────────────────────
# 3. Ensure gh is logged in
# ────────────────────────────────────────────────────────────────────────────
Write-Step 'بررسی لاگین GitHub CLI'
$authStatus = (gh auth status 2>&1 | Out-String)
if ($LASTEXITCODE -ne 0 -or $authStatus -match 'not logged') {
    Write-Fa 'gh لاگین نیست — وارد شو:'
    gh auth login --web
    if ($LASTEXITCODE -ne 0) { Write-Err 'لاگین ناموفق بود'; exit 1 }
}
Write-OK 'gh لاگین است'

# ────────────────────────────────────────────────────────────────────────────
# 4. git init (if needed) + add + commit
# ────────────────────────────────────────────────────────────────────────────
Write-Step 'git commit تغییرات'
if (-not (Test-Path '.git')) {
    git init
    git branch -M main
}
git add -A
$status = (git status --porcelain 2>&1 | Out-String).Trim()
if ($status) {
    $ts = Get-Date -Format 'yyyy-MM-dd HH:mm:ss'
    git commit -m "build: $ts" 2>&1 | Out-Null
    Write-OK 'تغییرات کامیت شدند'
} else {
    Write-OK 'تغییری برای کامیت نیست'
}

# ────────────────────────────────────────────────────────────────────────────
# 5. Ensure remote exists + push
# ────────────────────────────────────────────────────────────────────────────
Write-Step 'git push'
$remotes = (git remote 2>&1 | Out-String).Trim()
if (-not $remotes.Contains('origin')) {
    $user = (gh api user --jq .login 2>&1 | Out-String).Trim()
    if (-not $user) { Write-Err 'نام کاربری GitHub قابل خواندن نیست'; exit 1 }
    $repoUrl = "https://github.com/$user/$RepoName.git"
    Write-Fa "ساخت مخزن $RepoName روی GitHub..."
    gh repo create $RepoName --public --source=. --remote=origin --push 2>&1 | Out-Null
} else {
    git push -u origin main --force 2>&1 | Out-Null
}
Write-OK 'push انجام شد'

# ────────────────────────────────────────────────────────────────────────────
# 6. Trigger the workflow
# ────────────────────────────────────────────────────────────────────────────
Write-Step 'اجرای workflow بیلد'
gh workflow run $WorkflowName 2>&1 | Out-Null
if ($LASTEXITCODE -ne 0) { Write-Err 'اجرای workflow ناموفق بود'; exit 1 }
Write-OK 'workflow اجرا شد'

# ────────────────────────────────────────────────────────────────────────────
# 7. Find the run + watch it
# ────────────────────────────────────────────────────────────────────────────
Write-Step 'پیدا کردن run و صبر برای تکمیل'
Start-Sleep -Seconds 10
$runId = (gh run list --workflow $WorkflowName --limit 1 --json databaseId --jq '.[0].databaseId' 2>&1 | Out-String).Trim()
if (-not $runId) { Write-Err 'run پیدا نشد'; exit 1 }
Write-Fa "run id: $runId — صبر برای تکمیل (می‌تواند ۱۵-۳۰ دقیقه طول بکشد)..."

gh run watch $runId --exit-status 2>&1 | Out-Null
if ($LASTEXITCODE -ne 0) {
    Write-Err 'بیلد شکست خورد — لاگ خطا:'
    gh run view $runId --log-failed 2>&1
    exit 1
}
Write-OK 'بیلد موفق بود'

# ────────────────────────────────────────────────────────────────────────────
# 8. Download artifacts
# ────────────────────────────────────────────────────────────────────────────
Write-Step 'دانلود APK'
if (Test-Path $OutDir) { Remove-Item $OutDir -Recurse -Force }
New-Item -ItemType Directory -Path $OutDir -Force | Out-Null
gh run download $runId -D $OutDir 2>&1 | Out-Null
if ($LASTEXITCODE -ne 0) { Write-Err 'دانلود ناموفق بود'; exit 1 }
Write-OK "APKها در $OutDir ذخیره شدند"

# ────────────────────────────────────────────────────────────────────────────
# 9. Print result
# ────────────────────────────────────────────────────────────────────────────
Write-Step 'نتیجه نهایی'
$apks = Get-ChildItem -Path $OutDir -Filter '*.apk' -Recurse
if (-not $apks) { Write-Err 'هیچ APK پیدا نشد'; exit 1 }

Write-Host ''
Write-Host 'APKهای ساخته‌شده:' -ForegroundColor Green
foreach ($apk in $apks) {
    $sizeMB = [math]::Round($apk.Length / 1MB, 1)
    Write-Host ("  {0}  ({1} MB)" -f $apk.FullName, $sizeMB) -ForegroundColor White
}

$arm64 = $apks | Where-Object { $_.Name -match 'arm64-v8a' } | Select-Object -First 1
if ($arm64) {
    Write-Host ''
    Write-Host '✅ فایل نصب روی گوشی (اکثر گوشی‌های امروزی):' -ForegroundColor Green
    Write-Host "   $($arm64.FullName)" -ForegroundColor White
    Write-Host ''
    Write-Host 'انتقال به گوشی: کابل USB / Google Drive / تلگرام → روی APK ضربه بزن' -ForegroundColor Yellow
} else {
    Write-Host ''
    Write-Host '✅ APKها در پوشه زیر:' -ForegroundColor Green
    Write-Host "   $OutDir" -ForegroundColor White
}
