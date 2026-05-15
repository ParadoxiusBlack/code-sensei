Param(
    [string]$ProjectDir = "."
)

$ErrorActionPreference = "Stop"

$Root = (Resolve-Path $ProjectDir).Path
Set-Location $Root

$ExeName = "CodeSenseiGUI"
$PrimaryExePath = Join-Path $Root "dist\$ExeName.exe"
if (Test-Path $PrimaryExePath) {
    try {
        Remove-Item -Path $PrimaryExePath -Force
    } catch {
        $timestamp = Get-Date -Format "yyyyMMdd_HHmmss"
        $ExeName = "CodeSenseiGUI_$timestamp"
        Write-Host "[CodeSensei Build] Existing EXE is in use; building with alternate name: $ExeName" -ForegroundColor Yellow
    }
}

$Python = Join-Path $Root ".venv\Scripts\python.exe"
if (-not (Test-Path $Python)) {
    Write-Host "[CodeSensei Build] Missing venv Python: $Python" -ForegroundColor Red
    Write-Host "Create it with: python -m venv .venv"
    Write-Host "Then install deps with: .venv\Scripts\python.exe -m pip install -e `".[dev,gui,build]`""
    exit 1
}

Write-Host "[CodeSensei Build] Installing/updating build dependencies..." -ForegroundColor Cyan
& $Python -m pip install -e ".[dev,gui,build]"

Write-Host "[CodeSensei Build] Building standalone GUI executable..." -ForegroundColor Cyan
& $Python -m PyInstaller `
    --noconfirm `
    --clean `
    --onefile `
    --windowed `
    --name "$ExeName" `
    --paths "src" `
    --collect-submodules "code_sensei" `
    --collect-data "code_sensei" `
    --hidden-import "PyQt6.sip" `
    "src\code_sensei\gui_main.py"

if ($LASTEXITCODE -ne 0) {
    Write-Host "[CodeSensei Build] Build failed." -ForegroundColor Red
    exit $LASTEXITCODE
}

$OneFileOutput = Join-Path $Root "dist\$ExeName.exe"
$FolderedOutput = Join-Path $Root "dist\$ExeName\$ExeName.exe"

if (Test-Path $OneFileOutput) {
    Write-Host "[CodeSensei Build] Success (one-file): $OneFileOutput" -ForegroundColor Green
} elseif (Test-Path $FolderedOutput) {
    Write-Host "[CodeSensei Build] Success (one-dir): $FolderedOutput" -ForegroundColor Green
} else {
    Write-Host "[CodeSensei Build] Build completed but EXE not found in dist/." -ForegroundColor Yellow
}
