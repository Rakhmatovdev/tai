$ErrorActionPreference = 'Stop'
$projectRoot = Split-Path -Parent $PSScriptRoot
$pythonPath = Join-Path $projectRoot '.venv/Scripts/python.exe'
& $pythonPath -m PyInstaller --noconfirm --distpath (Join-Path $projectRoot 'dist') --workpath (Join-Path $projectRoot 'build/pyinstaller') (Join-Path $PSScriptRoot 'Brave.spec')
if ($LASTEXITCODE -ne 0) { throw 'Brave package build failed.' }
Copy-Item -LiteralPath (Join-Path $PSScriptRoot 'Install-Brave.ps1') -Destination (Join-Path $projectRoot 'dist/Install-Brave.ps1')
Copy-Item -LiteralPath (Join-Path $PSScriptRoot 'Install-Brave.vbs') -Destination (Join-Path $projectRoot 'dist/Install-Brave.vbs')
$ocrSource = Join-Path $env:LOCALAPPDATA 'Brave/ocr/tesseract'
if (Test-Path -LiteralPath (Join-Path $ocrSource 'tesseract.exe')) {
    $ocrTarget = Join-Path $projectRoot 'dist/Brave/ocr/tesseract'
    New-Item -ItemType Directory -Path $ocrTarget -Force | Out-Null
    Get-ChildItem -LiteralPath $ocrSource -File | Where-Object { $_.Extension -eq '.dll' -or $_.Name -eq 'tesseract.exe' } | ForEach-Object { Copy-Item -LiteralPath $_.FullName -Destination $ocrTarget }
    Copy-Item -LiteralPath (Join-Path $ocrSource 'tessdata') -Destination $ocrTarget -Recurse -Force
    Copy-Item -LiteralPath (Join-Path $PSScriptRoot 'OCR-NOTICE.txt') -Destination $ocrTarget
}
Write-Output 'Package ready in dist/Brave. Install-Brave.ps1 installs per-user without administrator privileges.'
