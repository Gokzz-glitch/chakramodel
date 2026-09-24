# AAAM one-command launcher.
# Run from PowerShell: .\start_aaam.ps1

$ErrorActionPreference = "Stop"
$projectRoot = Split-Path -Parent $MyInvocation.MyCommand.Path
$frontendRoot = Join-Path $projectRoot "frontend"
$wslDistro = "Ubuntu"
$windowsRoot = [System.IO.Path]::GetPathRoot($projectRoot)
$driveLetter = $windowsRoot.TrimEnd('\').TrimEnd(':').ToLowerInvariant()
$wslProject = "/mnt/$driveLetter/" + $projectRoot.Substring($windowsRoot.Length).TrimStart('\').Replace('\', '/')
$apiLog = Join-Path $projectRoot "aaam-api.log"
$apiErrorLog = Join-Path $projectRoot "aaam-api-error.log"
$webLog = Join-Path $projectRoot "aaam-web.log"
$webErrorLog = Join-Path $projectRoot "aaam-web-error.log"

function Stop-AAAM {
    Write-Host "`nStopping AAAM..." -ForegroundColor Yellow
    if ($script:apiProcess -and -not $script:apiProcess.HasExited) {
        Stop-Process -Id $script:apiProcess.Id -Force -ErrorAction SilentlyContinue
    }
    if ($script:webProcess -and -not $script:webProcess.HasExited) {
        Stop-Process -Id $script:webProcess.Id -Force -ErrorAction SilentlyContinue
    }
}

try {
    Set-Location $projectRoot
    wsl.exe -d $wslDistro -- true 2>$null
    if ($LASTEXITCODE -ne 0) {
        throw "WSL distribution '$wslDistro' was not found. Run 'wsl.exe -l -v' to inspect installed distributions."
    }
    if (-not (Test-Path (Join-Path $frontendRoot "node_modules"))) {
        Write-Host "Installing frontend dependencies..." -ForegroundColor Cyan
        Push-Location $frontendRoot
        npm install
        Pop-Location
    }

    Write-Host "Checking WSL model environment..." -ForegroundColor Cyan
    $venvCheck = wsl.exe -d $wslDistro -- bash -lc "test -x '$wslProject/.venv-aaam/bin/python' && echo ready || echo missing"
    if ($venvCheck.Trim() -ne "ready") {
        throw "WSL environment is missing. Create it in Ubuntu with: sudo apt-get install python3.12-venv; cd '$wslProject'; python3 -m venv .venv-aaam; . .venv-aaam/bin/activate; pip install -r requirements-aqi.txt"
    }
    $depsCheck = wsl.exe -d $wslDistro -- bash -lc "cd '$wslProject' && . .venv-aaam/bin/activate && python -c 'import fastapi, chronos' >/dev/null 2>&1; echo `$?"
    if ($depsCheck.Trim() -ne "0") {
        Write-Host "Installing AAAM WSL model dependencies..." -ForegroundColor Cyan
        wsl.exe -d $wslDistro -- bash -lc "cd '$wslProject' && . .venv-aaam/bin/activate && pip install -r requirements-aqi.txt"
        if ($LASTEXITCODE -ne 0) {
            throw "WSL dependency installation failed."
        }
    }

    Write-Host "Starting FastAPI + Chronos-2 service on http://127.0.0.1:8000..." -ForegroundColor Cyan
    $apiCommand = "cd '$wslProject' && . .venv-aaam/bin/activate && AAAM_DEVICE_MAP=auto python -m uvicorn aqi_backend.main:app --host 0.0.0.0 --port 8000"
    $script:apiProcess = Start-Process wsl.exe -ArgumentList @("-d", $wslDistro, "--", "bash", "-lc", $apiCommand) -RedirectStandardOutput $apiLog -RedirectStandardError $apiErrorLog -PassThru -WindowStyle Minimized

    $apiReady = $false
    for ($attempt = 1; $attempt -le 20; $attempt++) {
        Start-Sleep -Seconds 1
        try {
            $health = Invoke-RestMethod "http://127.0.0.1:8000/health" -TimeoutSec 2
            $apiReady = $true
            Write-Host ("API ready: model={0}, input={1}" -f $health.model, $health.input_source) -ForegroundColor Green
            break
        } catch {}
    }
    if (-not $apiReady) {
        throw "AAAM API did not become healthy. Check $apiLog"
    }

    Write-Host "Starting AAAM dashboard on http://localhost:5173..." -ForegroundColor Cyan
    $webCommand = "Set-Location '$frontendRoot'; npm run dev -- --host 0.0.0.0"
    $script:webProcess = Start-Process powershell.exe -ArgumentList @("-NoProfile", "-Command", $webCommand) -RedirectStandardOutput $webLog -RedirectStandardError $webErrorLog -PassThru -WindowStyle Minimized

    $webReady = $false
    for ($attempt = 1; $attempt -le 20; $attempt++) {
        Start-Sleep -Seconds 1
        try {
            $page = Invoke-WebRequest "http://127.0.0.1:5173" -UseBasicParsing -TimeoutSec 2
            if ($page.StatusCode -eq 200) {
                $webReady = $true
                Write-Host "Dashboard ready: http://localhost:5173" -ForegroundColor Green
                break
            }
        } catch {}
    }
    if (-not $webReady) {
        throw "AAAM dashboard did not become ready. Check $webLog"
    }

    Write-Host "`nAAAM is running. Press Ctrl+C to stop both services." -ForegroundColor Green
    Write-Host "Hardware telemetry: POST http://127.0.0.1:8000/api/telemetry"
    Write-Host "Input mode:        POST http://127.0.0.1:8000/api/source"
    while ($true) {
        if ($script:apiProcess.HasExited -or $script:webProcess.HasExited) {
            throw "One AAAM service stopped. Check aaam-api.log and aaam-web.log."
        }
        Start-Sleep -Seconds 2
    }
} finally {
    Stop-AAAM
}
