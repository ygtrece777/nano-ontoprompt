# One-shot local dev setup. Safe to run repeatedly: each step is skipped when already done.
# Invoked automatically by the VS Code "Full stack" launch config (preLaunchTask).
# NOTE: keep this file ASCII-only (Windows PowerShell 5.1 misreads UTF-8 without BOM).
# 'Continue': in PS 5.1, 'Stop' aborts on any native stderr output (e.g. harmless docker warnings).
# Native command failures are checked via $LASTEXITCODE instead.
$ErrorActionPreference = 'Continue'
$root = Split-Path -Parent $PSScriptRoot
$backend = Join-Path $root 'backend'
$frontend = Join-Path $root 'frontend'

function Step($msg) { Write-Host "==> $msg" -ForegroundColor Cyan }
function Fail($msg) { Write-Host "[setup] $msg" -ForegroundColor Red; exit 1 }
function FileHash($path) { (Get-FileHash $path -Algorithm SHA256).Hash }

# 1. Prerequisites
Step 'Checking prerequisites'
if (-not (Get-Command docker -ErrorAction SilentlyContinue)) { Fail 'Docker not found. Install Docker Desktop: winget install Docker.DockerDesktop' }
docker info *> $null
if ($LASTEXITCODE -ne 0) { Fail 'Docker Desktop is not running. Start it, wait until it is ready, then press F5 again.' }
if (-not (Get-Command npm -ErrorAction SilentlyContinue)) { Fail 'Node.js not found. Install Node 18+: winget install OpenJS.NodeJS.LTS' }

$python = $null
foreach ($cand in @(@('py', '-3.11'), @('python'))) {
    $exe = $cand[0]; $args_ = @($cand | Select-Object -Skip 1)
    if (Get-Command $exe -ErrorAction SilentlyContinue) {
        $ver = & $exe @args_ -c "import sys; print('%d.%d' % sys.version_info[:2])" 2>$null
        if ($LASTEXITCODE -eq 0 -and [version]$ver -ge [version]'3.11') { $python = $cand; break }
    }
}
if (-not $python) { Fail 'Python 3.11+ not found. Install it: winget install Python.Python.3.11' }

# 2. backend/.env from template (never overwrite an existing one)
$envFile = Join-Path $backend '.env'
if (-not (Test-Path $envFile)) {
    Step 'Creating backend/.env from backend/.env.dev.example'
    Copy-Item (Join-Path $backend '.env.dev.example') $envFile
}

# 3. Python venv + requirements (re-install only when requirements.txt changes)
$venvPy = Join-Path $backend '.venv\Scripts\python.exe'
if (-not (Test-Path $venvPy)) {
    Step 'Creating Python virtual environment (backend/.venv)'
    $exe = $python[0]; $args_ = @($python | Select-Object -Skip 1)
    & $exe @args_ -m venv (Join-Path $backend '.venv')
    if ($LASTEXITCODE -ne 0) { Fail 'Failed to create virtual environment.' }
}
$reqFile = Join-Path $backend 'requirements.txt'
$reqMarker = Join-Path $backend '.venv\.requirements.sha256'
$reqHash = FileHash $reqFile
if (-not (Test-Path $reqMarker) -or (Get-Content $reqMarker) -ne $reqHash) {
    Step 'Installing backend dependencies (first run takes a few minutes)'
    & $venvPy -m pip install -r $reqFile
    if ($LASTEXITCODE -ne 0) { Fail 'pip install failed.' }
    Set-Content $reqMarker $reqHash
}

# 4. Frontend deps (clean install only when package-lock.json changes)
$lockFile = Join-Path $frontend 'package-lock.json'
$lockMarker = Join-Path $frontend 'node_modules\.package-lock.sha256'
$lockHash = FileHash $lockFile
if (-not (Test-Path $lockMarker) -or (Get-Content $lockMarker) -ne $lockHash) {
    # npm ci wipes node_modules; a running Vite locks native binaries and would leave it half-deleted
    if (Get-NetTCPConnection -LocalPort 5173 -State Listen -ErrorAction SilentlyContinue) {
        Fail 'Frontend dev server is running on port 5173. Stop it first (Shift+F5), then retry.'
    }
    Step 'Installing frontend dependencies (npm ci)'
    Push-Location $frontend
    try { npm ci; if ($LASTEXITCODE -ne 0) { Fail 'npm ci failed.' } } finally { Pop-Location }
    Set-Content $lockMarker $lockHash
}

# 5. Infrastructure containers; --wait blocks until they are up (Postgres/Redis until healthy)
Step 'Starting infrastructure containers'
docker compose -f (Join-Path $root 'docker-compose.dev.yml') up -d --wait
if ($LASTEXITCODE -ne 0) { Fail 'docker compose up failed. See the output above.' }

Write-Host '==> Setup complete' -ForegroundColor Green
