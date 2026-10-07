<#
.SYNOPSIS
    One-Click Launcher for AGE (MY BEST FRIEND AI).
.DESCRIPTION
    Launches the AGE Core WebSocket server and the Flutter Windows Desktop UI.
    Auto-detects running components, provides graceful startup, and displays live status.
.PARAMETER Headless
    Start Core WebSocket server only without opening the Flutter UI.
.PARAMETER UIOnly
    Launch the Flutter UI only (Core will auto-connect or auto-spawn if configured).
.EXAMPLE
    .\run.ps1
    .\run.ps1 -Headless
#>

[CmdletBinding()]
param(
    [switch]$Headless,
    [switch]$UIOnly
)

$ErrorActionPreference = "Stop"

$VenvPython = Join-Path $PSScriptRoot ".venv\Scripts\python.exe"

if (-not (Test-Path $VenvPython)) {
    Write-Host "[ERROR] Virtual environment not found. Please run .\setup.ps1 first." -ForegroundColor Red
    exit 1
}

Write-Host "============================================================" -ForegroundColor Cyan
Write-Host "       Starting AGE - Personal Offline Voice Assistant       " -ForegroundColor Cyan
Write-Host "============================================================" -ForegroundColor Cyan

# Function to test TCP port
function Test-PortOpen {
    param([string]$Address = "127.0.0.1", [int]$Port = 8765)
    $tcp = New-Object System.Net.Sockets.TcpClient
    try {
        $ar = $tcp.BeginConnect($Address, $Port, $null, $null)
        $wait = $ar.AsyncWaitHandle.WaitOne(400, $false)
        if ($wait -and $tcp.Connected) {
            $tcp.EndConnect($ar)
            return $true
        }
        return $false
    } catch {
        return $false
    } finally {
        $tcp.Close()
    }
}

# 1. Start Core Server if not UI-only
$CoreStarted = $false
if (-not $UIOnly) {
    if (Test-PortOpen -Port 8765) {
        Write-Host "[CORE] Core WebSocket server is already running on 127.0.0.1:8765." -ForegroundColor Green
    } else {
        Write-Host "[CORE] Starting Core WebSocket server in background..." -ForegroundColor Yellow
        $LogDir = Join-Path $PSScriptRoot "data\logs"
        if (-not (Test-Path $LogDir)) { New-Item -ItemType Directory -Path $LogDir -Force | Out-Null }
        $CoreLog = Join-Path $LogDir "core_runner.log"

        $CoreProc = Start-Process -FilePath $VenvPython `
            -ArgumentList "-m core.server.runner" `
            -WorkingDirectory $PSScriptRoot `
            -RedirectStandardOutput $CoreLog `
            -RedirectStandardError $CoreLog `
            -PassThru

        # Wait for port 8765 to bind
        $attempts = 0
        while ($attempts -lt 15) {
            Start-Sleep -Milliseconds 500
            if (Test-PortOpen -Port 8765) {
                $CoreStarted = $true
                break
            }
            $attempts++
        }

        if ($CoreStarted) {
            Write-Host "[CORE] Core Server online (PID: $($CoreProc.Id)) -> ws://127.0.0.1:8765" -ForegroundColor Green
        } else {
            Write-Warning "Core Server starting slowly or encountered an error. Check $CoreLog."
        }
    }
}

# 2. Display System Status & Hotkeys
Write-Host ""
Write-Host "Status & Key Shortcuts:" -ForegroundColor White
Write-Host "  * Emergency Stop:   Ctrl+Shift+Esc (Immediate hard kill of mic, camera, mouse)" -ForegroundColor Red
Write-Host "  * Wake Word:        'Hey AGE' (Porcupine wake word)" -ForegroundColor Yellow
Write-Host "  * Push-to-Talk:     Ctrl+Space (Voice fallback trigger)" -ForegroundColor Yellow
Write-Host "  * Offline Security: 100% Local (0.0.0.0 rejected, no telemetry)" -ForegroundColor Mint
Write-Host ""

if ($Headless) {
    Write-Host "[MODE] Running in Headless Core mode. Press Ctrl+C in terminal to stop." -ForegroundColor Cyan
    while ($true) {
        Start-Sleep -Seconds 2
    }
    exit 0
}

# 3. Launch Flutter Desktop UI
$UiExe = Join-Path $PSScriptRoot "ui\build\windows\x64\runner\Release\age_ui.exe"
if (Test-Path $UiExe) {
    Write-Host "[UI] Launching AGE Desktop Release binary..." -ForegroundColor Cyan
    Start-Process -FilePath $UiExe -WorkingDirectory (Join-Path $PSScriptRoot "ui")
} elseif (Get-Command flutter -ErrorAction SilentlyContinue) {
    Write-Host "[UI] Launching AGE Flutter Desktop via 'flutter run'..." -ForegroundColor Cyan
    Push-Location (Join-Path $PSScriptRoot "ui")
    try {
        flutter run -d windows
    } finally {
        Pop-Location
    }
} else {
    Write-Host "[INFO] Flutter SDK not found in PATH to launch UI automatically." -ForegroundColor Yellow
    Write-Host "       The Core WebSocket server is active on ws://127.0.0.1:8765." -ForegroundColor Green
    Write-Host "       You can connect any authorized client or build ui/ with Flutter." -ForegroundColor White
}
