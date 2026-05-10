param(
    [switch]$SkipInstall
)

$ErrorActionPreference = 'Stop'

Set-Location $PSScriptRoot

function Get-VenvRoot {
    foreach ($candidate in @('.venv', 'venv')) {
        if (Test-Path $candidate) {
            return (Resolve-Path $candidate).Path
        }
    }

    return $null
}

function Get-VenvPython {
    param(
        [string]$VenvRoot
    )

    $pythonPath = Join-Path $VenvRoot 'Scripts\python.exe'
    if (-not (Test-Path $pythonPath)) {
        throw "Virtual environment Python not found: $pythonPath"
    }

    return $pythonPath
}

function Test-OpenPort {
    param(
        [int]$Port
    )

    try {
        return [bool](Get-NetTCPConnection -LocalPort $Port -State Listen -ErrorAction Stop)
    } catch {
        return $false
    }
}

function Show-PortStatus {
    param(
        [int[]]$Ports
    )

    foreach ($port in $Ports) {
        if (Test-OpenPort -Port $port) {
            Write-Host "[OK] Port $port is already listening"
        } else {
            Write-Host "[INFO] Port $port is not listening yet"
        }
    }
}

function Wait-ForPort {
    param(
        [int]$Port,
        [int]$TimeoutSeconds = 30
    )

    $deadline = (Get-Date).AddSeconds($TimeoutSeconds)
    while ((Get-Date) -lt $deadline) {
        if (Test-OpenPort -Port $Port) {
            return $true
        }

        Start-Sleep -Milliseconds 500
    }

    return $false
}

$venvRoot = Get-VenvRoot
if (-not $venvRoot) {
    Write-Host '[Setup] No virtual environment found. Creating .venv...'
    python -m venv .venv
    $venvRoot = (Resolve-Path .venv).Path
}

$venvPython = Get-VenvPython -VenvRoot $venvRoot

Write-Host "[Setup] Using virtual environment: $venvRoot"
Show-PortStatus -Ports @(1234, 1235, 11235, 8765, 8080)

if (-not $SkipInstall) {
    Write-Host '[Setup] Installing Python requirements...'
    & $venvPython -m pip install -r requirements.txt
}

Write-Host '[Setup] Verifying runtime imports...'
& $venvPython -c "import aiohttp, websockets; print('runtime imports ok')"

if ((Test-OpenPort -Port 8765) -or (Test-OpenPort -Port 8080)) {
    Write-Host '[Start] Backend ports already active. Skipping bridge launch.'
    Show-PortStatus -Ports @(8765, 8080)
    exit 0
}

Write-Host '[Start] Launching NovelForge bridge in a background process...'
Start-Process -FilePath $venvPython -ArgumentList 'bridge.py' -WorkingDirectory $PSScriptRoot

if ((Wait-ForPort -Port 8080 -TimeoutSeconds 45) -and (Wait-ForPort -Port 8765 -TimeoutSeconds 45)) {
    Write-Host '[OK] NovelForge bridge started successfully.'
    Show-PortStatus -Ports @(8765, 8080, 11235, 1234, 1235)
} else {
    Write-Host '[WARN] Bridge launch was requested, but one or more ports did not open in time.'
    Show-PortStatus -Ports @(8765, 8080, 11235, 1234, 1235)
}