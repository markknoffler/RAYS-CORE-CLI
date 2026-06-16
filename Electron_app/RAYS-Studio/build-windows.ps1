# Build RAYS Studio for Windows (NSIS installer). Run on Windows with Python 3.10+ and Node 18+.
$ErrorActionPreference = "Stop"
$Root = Split-Path -Parent $MyInvocation.MyCommand.Path
$Epoch = [int][double]::Parse((Get-Date -UFormat %s))
@{ epoch = "$Epoch" } | ConvertTo-Json | Set-Content -Path (Join-Path $Root "desktop\electron\install-epoch.json") -Encoding utf8
Write-Host "==> Install epoch for this build: $Epoch"
Push-Location (Join-Path $Root "ui")
npm ci
npm run build
Pop-Location
Push-Location (Join-Path $Root "desktop")
npm ci
npm run dist:win
Pop-Location
Write-Host "Windows artifacts under: $Root\desktop\release"
Get-ChildItem (Join-Path $Root "desktop\release") -Filter *.exe -ErrorAction SilentlyContinue
