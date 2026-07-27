# Checks ComfyUI, Ollama, and image-fe (FE/BE) and starts whichever isn't already running.
# Run from anywhere: powershell -File start-all.ps1

$ErrorActionPreference = "Stop"
$root = $PSScriptRoot
$comfyDir = Join-Path $root "comfyui-rocm"
$imageFeDir = Join-Path $root "image-fe"

function Test-PortOpen {
    param([int]$Port, [int]$TimeoutMs = 1000)
    try {
        $client = New-Object System.Net.Sockets.TcpClient
        $result = $client.BeginConnect("localhost", $Port, $null, $null)
        $ok = $result.AsyncWaitHandle.WaitOne($TimeoutMs) -and $client.Connected
        $client.Close()
        return $ok
    } catch {
        return $false
    }
}

function Wait-ForPort {
    param([int]$Port, [int]$TimeoutSeconds)
    $elapsed = 0
    while (-not (Test-PortOpen -Port $Port) -and $elapsed -lt $TimeoutSeconds) {
        Start-Sleep -Seconds 2
        $elapsed += 2
    }
    return Test-PortOpen -Port $Port
}

function Test-DockerRunning {
    docker info *>$null
    return ($LASTEXITCODE -eq 0)
}

Write-Host "=== Ollama (LLM, port 11434) ===" -ForegroundColor Cyan
if (Test-PortOpen -Port 11434) {
    Write-Host "already running" -ForegroundColor Green
} else {
    Write-Host "not running -- starting..." -ForegroundColor Yellow
    Start-Process -FilePath "ollama" -ArgumentList "serve" -WindowStyle Hidden
    if (Wait-ForPort -Port 11434 -TimeoutSeconds 15) {
        Write-Host "started" -ForegroundColor Green
    } else {
        Write-Host "did not come up within 15s -- check it manually" -ForegroundColor Red
    }
}

Write-Host "`n=== ComfyUI-ROCm (port 8188) ===" -ForegroundColor Cyan
if (Test-PortOpen -Port 8188) {
    Write-Host "already running" -ForegroundColor Green
} else {
    Write-Host "not running -- starting (opens its own console window)..." -ForegroundColor Yellow
    Start-Process -FilePath (Join-Path $comfyDir "comfyui-rocm.bat") -WorkingDirectory $comfyDir
    if (Wait-ForPort -Port 8188 -TimeoutSeconds 90) {
        Write-Host "started" -ForegroundColor Green
    } else {
        Write-Host "still starting (model/ROCm init can take a while) -- check its console window" -ForegroundColor Yellow
    }
}

Write-Host "`n=== image-fe (FE/BE, port 8080) ===" -ForegroundColor Cyan
if (Test-PortOpen -Port 8080) {
    Write-Host "already running" -ForegroundColor Green
} else {
    Write-Host "not running -- starting..." -ForegroundColor Yellow
    if (-not (Test-DockerRunning)) {
        Write-Host "Docker daemon not running -- launching Docker Desktop..." -ForegroundColor Yellow
        $dockerDesktop = "$env:ProgramFiles\Docker\Docker\Docker Desktop.exe"
        if (Test-Path $dockerDesktop) {
            Start-Process $dockerDesktop
            $elapsed = 0
            while (-not (Test-DockerRunning) -and $elapsed -lt 90) {
                Start-Sleep -Seconds 3
                $elapsed += 3
            }
        } else {
            Write-Host "Could not find Docker Desktop at the default path -- start it manually, then re-run this script." -ForegroundColor Red
        }
    }

    if (Test-DockerRunning) {
        Push-Location $imageFeDir
        docker compose up -d
        Pop-Location
        if (Wait-ForPort -Port 8080 -TimeoutSeconds 30) {
            Write-Host "started" -ForegroundColor Green
        } else {
            Write-Host "did not come up within 30s -- check `"docker compose logs image-fe`"" -ForegroundColor Red
        }
    } else {
        Write-Host "Docker still not available -- skipped starting image-fe" -ForegroundColor Red
    }
}

Write-Host "`n=== Summary ===" -ForegroundColor Cyan
Write-Host "Ollama    (11434): $(if (Test-PortOpen -Port 11434) { 'online' } else { 'offline' })"
Write-Host "ComfyUI   (8188):  $(if (Test-PortOpen -Port 8188) { 'online' } else { 'offline' })"
Write-Host "image-fe  (8080):  $(if (Test-PortOpen -Port 8080) { 'online' } else { 'offline' })"
