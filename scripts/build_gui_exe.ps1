Param(
    [string]$ProjectDir = "."
)

$ErrorActionPreference = "Stop"

$Root = (Resolve-Path $ProjectDir).Path
Set-Location $Root

$ExeName = "CodeSenseiGUI"
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

# Clean old builds
if (Test-Path "dist") {
    Remove-Item -Path "dist" -Recurse -Force -ErrorAction SilentlyContinue
}
if (Test-Path "build") {
    Remove-Item -Path "build" -Recurse -Force -ErrorAction SilentlyContinue
}

& $Python -m PyInstaller `
    --noconfirm `
    --onedir `
    --windowed `
    --name "$ExeName" `
    --paths "src" `
    --hidden-import "PyQt6.sip" `
    --hidden-import "chromadb" `
    --hidden-import "langchain" `
    "src\code_sensei\gui_main.py"

if ($LASTEXITCODE -ne 0) {
    Write-Host "[CodeSensei Build] Build failed." -ForegroundColor Red
    exit $LASTEXITCODE
}

$BuildOutput = Join-Path $Root "dist\$ExeName"
if (Test-Path $BuildOutput) {
    Write-Host "[CodeSensei Build] Success! Built to: $BuildOutput" -ForegroundColor Green
    $ExeFile = Join-Path $BuildOutput "$ExeName.exe"
    if (Test-Path $ExeFile) {
        Write-Host "[CodeSensei Build] Executable ready at: $ExeFile" -ForegroundColor Green
    }
} else {
    Write-Host "[CodeSensei Build] Build completed but output not found." -ForegroundColor Yellow
}
