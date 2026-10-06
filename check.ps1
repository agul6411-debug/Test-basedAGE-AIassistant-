# ==============================================================================
# AGE - Quality and Security Verification Script
# Runs: ruff, pytest, bandit, pip-audit
# Exit Code: 0 on success, 1 on failure
# ==============================================================================

$ErrorActionPreference = "Stop"

$VenvPython = Join-Path $PSScriptRoot ".venv\Scripts\python.exe"
$VenvRuff   = Join-Path $PSScriptRoot ".venv\Scripts\ruff.exe"
$VenvPytest = Join-Path $PSScriptRoot ".venv\Scripts\pytest.exe"
$VenvBandit = Join-Path $PSScriptRoot ".venv\Scripts\bandit.exe"
$VenvAudit  = Join-Path $PSScriptRoot ".venv\Scripts\pip-audit.exe"

if (-not (Test-Path $VenvPython)) {
    Write-Host "[ERROR] Virtual environment not found at .venv" -ForegroundColor Red
    exit 1
}

Write-Host "==================================================" -ForegroundColor Cyan
Write-Host "  AGE Quality & Security Checks" -ForegroundColor Cyan
Write-Host "==================================================" -ForegroundColor Cyan

# 1. Ruff Lint
Write-Host "`n[1/4] Running Ruff linter..." -ForegroundColor Yellow
& $VenvRuff check $PSScriptRoot
if ($LASTEXITCODE -ne 0) {
    Write-Host "[FAIL] Ruff check failed!" -ForegroundColor Red
    exit 1
}
Write-Host "[PASS] Ruff check clean." -ForegroundColor Green

# 2. Pytest Suite
Write-Host "`n[2/4] Running Pytest test suite..." -ForegroundColor Yellow
& $VenvPytest $PSScriptRoot -v
if ($LASTEXITCODE -ne 0) {
    Write-Host "[FAIL] Pytest tests failed!" -ForegroundColor Red
    exit 1
}
Write-Host "[PASS] All unit tests passed." -ForegroundColor Green

# 3. Bandit Security Scan
Write-Host "`n[3/4] Running Bandit static security analysis..." -ForegroundColor Yellow
& $VenvBandit -r (Join-Path $PSScriptRoot "core") (Join-Path $PSScriptRoot "hand_mouse")
if ($LASTEXITCODE -ne 0) {
    Write-Host "[FAIL] Bandit security check failed!" -ForegroundColor Red
    exit 1
}
Write-Host "[PASS] Bandit security scan clean." -ForegroundColor Green

# 4. Pip-Audit Dependency Scan
Write-Host "`n[4/4] Running Pip-Audit dependency vulnerability scan..." -ForegroundColor Yellow
$LockFile = Join-Path $PSScriptRoot "requirements.lock"
& $VenvAudit -r $LockFile
if ($LASTEXITCODE -ne 0) {
    Write-Host "[FAIL] Pip-audit vulnerability scan failed!" -ForegroundColor Red
    exit 1
}
Write-Host "[PASS] Pip-audit reported 0 vulnerabilities." -ForegroundColor Green

Write-Host "`n==================================================" -ForegroundColor Cyan
Write-Host "  ALL CHECKS PASSED CLEANLY (Code 0)" -ForegroundColor Green
Write-Host "==================================================" -ForegroundColor Cyan
exit 0
