param([switch]$Rollback,[string]$InstallDirectory,[switch]$SkipShortcut)
$ErrorActionPreference = 'Stop'
$installRoot = if ($InstallDirectory) { [IO.Path]::GetFullPath($InstallDirectory) } else { Join-Path $env:LOCALAPPDATA 'Programs/BraveAssistant' }
$manifestPath = Join-Path $installRoot 'installation.json'
New-Item -ItemType Directory -Path $installRoot -Force | Out-Null
$previous = $null
if (Test-Path -LiteralPath $manifestPath) { $previous = Get-Content -LiteralPath $manifestPath -Raw | ConvertFrom-Json }
if ($Rollback) {
    if (-not $previous -or -not $previous.previous -or -not (Test-Path -LiteralPath (Join-Path $previous.previous 'Brave.exe'))) { throw 'No previous installation is available.' }
    $versionPath = $previous.previous
} else {
    $sourcePath = Join-Path $PSScriptRoot 'Brave'
    if (-not (Test-Path -LiteralPath (Join-Path $sourcePath 'Brave.exe'))) { throw 'Place this installer next to the built Brave folder.' }
    $versionPath = Join-Path $installRoot ('version-' + (Get-Date -Format 'yyyyMMdd-HHmmss-fff'))
    Copy-Item -LiteralPath $sourcePath -Destination $versionPath -Recurse
}
if (-not $SkipShortcut) {
    $shell = New-Object -ComObject WScript.Shell
    $shortcutPath = Join-Path ([Environment]::GetFolderPath('Programs')) 'Brave Assistant.lnk'
    $shortcut = $shell.CreateShortcut($shortcutPath)
    $shortcut.TargetPath = Join-Path $versionPath 'Brave.exe'
    $shortcut.WorkingDirectory = $versionPath
    $shortcut.Save()
}
$lastPath = if ($previous) { $previous.current } else { $null }
@{current=$versionPath; previous=$lastPath} | ConvertTo-Json | Set-Content -LiteralPath $manifestPath -Encoding UTF8
Write-Output ('Brave is ready: ' + $versionPath + '. Settings remain in LocalAppData/Brave.')
