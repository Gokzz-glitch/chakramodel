# ChakraModel one-click launcher for Windows PowerShell
# Run from PowerShell as: .\start_chakramodel.ps1

$ErrorActionPreference = "Stop"

$projectRoot = Split-Path -Parent $MyInvocation.MyCommand.Path
Set-Location $projectRoot

Write-Host "[1/3] Activating virtual environment..." -ForegroundColor Cyan
. .\.venv\Scripts\Activate.ps1

Write-Host "[2/3] Installing Python dependencies (if needed)..." -ForegroundColor Cyan
pip install -r requirements.txt

Write-Host "[3/3] Starting ChakraModel Gradio app..." -ForegroundColor Cyan
Write-Host "Open: http://127.0.0.1:7860/" -ForegroundColor Green
python src/app.py
