# Build one-file executable with PyInstaller.
# Usage:  powershell -File build_exe.ps1
# Output: dist/lx2al.exe

$ErrorActionPreference = "Stop"
$root = Split-Path -Parent $MyInvocation.MyCommand.Path
Set-Location $root

$venv = Join-Path $root ".venv-build"
$py = Join-Path $venv "Scripts\python.exe"
if (-not (Test-Path $py)) {
    Write-Host "creating venv..."
    & D:\Anaconda\python.exe -m venv $venv
}
& $py -m pip install -q -U pip pyinstaller

Write-Host "building lx2al.exe ..."
& $py -m PyInstaller --onefile --name lx2al --clean -y `
    --distpath dist --workpath build --specpath build `
    entry.py

$exe = Join-Path $root "dist\lx2al.exe"
if (-not (Test-Path $exe)) { throw "build failed: $exe missing" }
Write-Host "OK $exe ($([math]::Round((Get-Item $exe).Length/1MB, 2)) MB)"
