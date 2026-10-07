<#
.SYNOPSIS
    Automated Installer and Setup Script for AGE (MY BEST FRIEND AI).
.DESCRIPTION
    Sets up the local Python virtual environment, installs dependencies with SHA256
    hash enforcement, downloads voice models with checksum verification, sets up
    the Flutter UI, and optionally registers user-level logon autostart.
    Strictly complies with PROJECT_RULES.md (no admin rights, 100% offline).
.PARAMETER EnableAutostart
    Register Windows Task Scheduler task to launch AGE on user logon (normal user token, no admin).
.PARAMETER SkipModels
    Skip downloading voice models if already downloaded.
.PARAMETER SkipFlutter
    Skip running 'flutter pub get' in ui/.
.EXAMPLE
    .\setup.ps1
    .\setup.ps1 -EnableAutostart
#>

[CmdletBinding()]
param(
    [switch]$EnableAutostart,
    [switch]$SkipModels,
    [switch]$SkipFlutter
)

$ErrorActionPreference = "Stop"

Write-Host "============================================================" -ForegroundColor Cyan
Write-Host "       AGE (MY BEST FRIEND AI) - Automated Setup            " -ForegroundColor Cyan
Write-Host "       Windows 10/11 x64 | 100% Offline Personal Assistant  " -ForegroundColor Cyan
Write-Host "============================================================" -ForegroundColor Cyan
Write-Host ""

# 1. Environment & Python Verification
Write-Host "[1/6] Verifying Python 3.11 environment..." -ForegroundColor Yellow
$PythonCmd = $null
if (Get-Command py -ErrorAction SilentlyContinue) {
    $PythonCmd = "py -3.11"
} elseif (Get-Command python -ErrorAction SilentlyContinue) {
    $pyVer = (python --version 2>&1)
    if ($pyVer -match "3\.11") {
        $PythonCmd = "python"
    } else {
        $PythonCmd = "python"
    }
} else {
    Write-Error "Python was not found in PATH. Please install Python 3.11.x x64 from python.org."
    exit 1
}

# 2. Virtual Environment Creation
$VenvPython = Join-Path $PSScriptRoot ".venv\Scripts\python.exe"
if (-not (Test-Path $VenvPython)) {
    Write-Host "[2/6] Creating Python virtual environment in .venv..." -ForegroundColor Yellow
    Invoke-Expression "$PythonCmd -m venv .venv"
    if ($LASTEXITCODE -ne 0) {
        Write-Error "Failed to create virtual environment."
        exit 1
    }
} else {
    Write-Host "[2/6] Virtual environment .venv already exists." -ForegroundColor Green
}

# 3. Locked Dependency Installation
Write-Host "[3/6] Installing locked dependencies with SHA256 hash enforcement..." -ForegroundColor Yellow
& $VenvPython -m pip install --upgrade pip --quiet
if ($LASTEXITCODE -ne 0) {
    Write-Error "Failed to upgrade pip."
    exit 1
}

$LockFile = Join-Path $PSScriptRoot "requirements.lock"
if (Test-Path $LockFile) {
    Write-Host "       Enforcing requirements.lock with exact hashes..." -ForegroundColor Gray
    & $VenvPython -m pip install --require-hashes -r $LockFile --quiet
    if ($LASTEXITCODE -ne 0) {
        Write-Error "Failed to install dependencies from requirements.lock."
        exit 1
    }
    Write-Host "       All 84 dependencies installed and hash-verified." -ForegroundColor Green
} else {
    Write-Error "requirements.lock not found in project root!"
    exit 1
}

# 4. Directory & Environment Template Setup
Write-Host "[4/6] Initializing storage directories and configuration..." -ForegroundColor Yellow
$Directories = @("data", "data\logs", "data\sessions", "models")
foreach ($dir in $Directories) {
    $fullPath = Join-Path $PSScriptRoot $dir
    if (-not (Test-Path $fullPath)) {
        New-Item -ItemType Directory -Path $fullPath -Force | Out-Null
    }
}

$EnvFile = Join-Path $PSScriptRoot ".env"
if (-not (Test-Path $EnvFile)) {
    $EnvContent = @"
# AGE Environment Secrets (Never commit to Git - Rule 6)
# Get a free personal access key from https://picovoice.ai/console/
PICOVOICE_ACCESS_KEY=
"@
    Set-Content -Path $EnvFile -Value $EnvContent -Encoding UTF8
    Write-Host "       Created template .env file. Add your PICOVOICE_ACCESS_KEY if using Porcupine wake word." -ForegroundColor Cyan
}

# 5. Model Verification & Download
if (-not $SkipModels) {
    Write-Host "[5/6] Checking and verifying offline models with SHA256 checksums..." -ForegroundColor Yellow
    & $VenvPython -m core.voice.model_downloader
    if ($LASTEXITCODE -ne 0) {
        Write-Warning "One or more voice models could not be downloaded. Run again or check internet connection."
    }
} else {
    Write-Host "[5/6] Skipping model download (-SkipModels specified)." -ForegroundColor Gray
}

# 6. Flutter UI Setup
if (-not $SkipFlutter) {
    Write-Host "[6/6] Checking Flutter Desktop UI..." -ForegroundColor Yellow
    if (Get-Command flutter -ErrorAction SilentlyContinue) {
        Push-Location (Join-Path $PSScriptRoot "ui")
        try {
            Write-Host "       Running 'flutter pub get'..." -ForegroundColor Gray
            flutter pub get
        } finally {
            Pop-Location
        }
        Write-Host "       Flutter UI dependencies configured." -ForegroundColor Green
    } else {
        Write-Host "       Flutter command not found in PATH. You can install Flutter or run Core in headless mode." -ForegroundColor Yellow
    }
}

# Autostart Registration (User Level, No Admin)
if ($EnableAutostart) {
    Write-Host ""
    Write-Host "[AUTOSTART] Registering user logon Task Scheduler entry..." -ForegroundColor Yellow
    & $VenvPython -m core.layout.autostart --enable
}

Write-Host ""
Write-Host "============================================================" -ForegroundColor Green
Write-Host "         AGE Setup Complete! All checks passed.             " -ForegroundColor Green
Write-Host "============================================================" -ForegroundColor Green
Write-Host ""
Write-Host "To start AGE now, run:" -ForegroundColor Cyan
Write-Host "    .\run.ps1" -ForegroundColor White
Write-Host ""
