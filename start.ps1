$ErrorActionPreference = 'Stop'
$projectDir = $PSScriptRoot
$environmentPath = Join-Path $projectDir '.venv\pyvenv.cfg'
if (-not (Test-Path -LiteralPath $environmentPath)) {
    throw 'Python muhiti topilmadi. Avval .venv muhitini tayyorlang.'
}
$logDir = Join-Path $projectDir 'logs'
New-Item -ItemType Directory -Path $logDir -Force | Out-Null
$launcherPath = Join-Path $projectDir 'launch_brave.vbs'
Start-Process -FilePath (Join-Path $env:WINDIR 'System32\wscript.exe') `
    -ArgumentList ('"' + $launcherPath + '"') -WorkingDirectory $projectDir -WindowStyle Hidden
