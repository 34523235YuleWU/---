$ErrorActionPreference = "Stop"

$projectRoot = Split-Path -Parent $MyInvocation.MyCommand.Path
Set-Location $projectRoot

Write-Host "Checking PyInstaller..."
$hasPyInstaller = python -c "import importlib.util; print(importlib.util.find_spec('PyInstaller') is not None)"
if ($hasPyInstaller.Trim() -ne "True") {
    Write-Host "Installing PyInstaller..."
    python -m pip install pyinstaller
}

Write-Host "Installing app dependencies..."
python -m pip install -r requirements.txt

Write-Host "Cleaning old build output..."
if (Test-Path -LiteralPath "build") {
    Remove-Item -LiteralPath "build" -Recurse -Force
}
if (Test-Path -LiteralPath "dist") {
    Remove-Item -LiteralPath "dist" -Recurse -Force
}
if (Test-Path -LiteralPath "SichuanMahjong.spec") {
    Remove-Item -LiteralPath "SichuanMahjong.spec" -Force
}

Write-Host "Building Windows app..."
python -m PyInstaller `
    --noconsole `
    --name "SichuanMahjong" `
    --add-data "assets;assets" `
    main.py

Write-Host ""
Write-Host "Build complete:"
Write-Host "$projectRoot\dist\SichuanMahjong\SichuanMahjong.exe"

if (Test-Path -LiteralPath "SichuanMahjong.spec") {
    Remove-Item -LiteralPath "SichuanMahjong.spec" -Force
}
if (Test-Path -LiteralPath "build") {
    Remove-Item -LiteralPath "build" -Recurse -Force
}
