# Bundle rays-core + bridge into a single executable for the desktop app (Windows).
$ErrorActionPreference = "Stop"

$ScriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
$DesktopDir = Split-Path -Parent $ScriptDir
$StudioRoot = Split-Path -Parent $DesktopDir
$MonorepoRoot = (Resolve-Path (Join-Path $StudioRoot "..\..")).Path
$BackendOut = Join-Path $DesktopDir "resources\backend"
$WorkDir = Join-Path $DesktopDir "resources\backend-build"
$VenvDir = Join-Path $DesktopDir "resources\bundle-venv"

Write-Host "==> RAYS Studio: bundling Python backend"
Write-Host "    Studio: $StudioRoot"
Write-Host "    Monorepo: $MonorepoRoot"

if (Test-Path $BackendOut) { Remove-Item -Recurse -Force $BackendOut }
if (Test-Path $WorkDir) { Remove-Item -Recurse -Force $WorkDir }
New-Item -ItemType Directory -Force -Path $BackendOut | Out-Null

Push-Location $MonorepoRoot
try {
  if (-not (Test-Path $VenvDir)) {
    python -m venv $VenvDir
  }
  & (Join-Path $VenvDir "Scripts\Activate.ps1")
  python -m pip install -q -U pip wheel
  python -m pip install -q -e ".[studio,dev]"
  python -m pip install -q "onnxruntime>=1.16,<2" "tokenizers>=0.15,<1"

  $Spec = Join-Path $DesktopDir "pyinstaller\rays-bridge.spec"
  pyinstaller $Spec `
    --distpath $BackendOut `
    --workpath $WorkDir `
    --noconfirm

  $BackendBin = Join-Path $BackendOut "rays-gui-bridge.exe"
  if (-not (Test-Path $BackendBin)) {
    throw "PyInstaller did not produce $BackendBin"
  }

  Write-Host "==> Backend bundle ready: $BackendBin"
  Get-Item $BackendBin | Format-List FullName, Length
}
finally {
  Pop-Location
}
