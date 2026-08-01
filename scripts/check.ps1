[CmdletBinding()]
param()

$ErrorActionPreference = 'Stop'
$repoRoot = Split-Path -Parent $PSScriptRoot
$python = Join-Path $repoRoot '.venv\Scripts\python.exe'
$nodeCommand = Get-Command node -ErrorAction SilentlyContinue
$nodePath = if ($nodeCommand) { $nodeCommand.Source } else { $null }

if (-not $nodePath) {
    $codexNode = Join-Path $env:USERPROFILE '.cache\codex-runtimes\codex-primary-runtime\dependencies\node\bin\node.exe'
    if (Test-Path -LiteralPath $codexNode) {
        $nodePath = $codexNode
    }
}

Set-Location $repoRoot

if (-not (Test-Path -LiteralPath $python)) {
    throw 'Missing .venv. Run scripts/dev.cmd first.'
}
if (-not $nodePath) {
    throw 'Node.js was not found; PWA checks cannot run.'
}

Write-Host '1/4 Python dependency integrity'
& $python -m pip check

Write-Host '2/4 Python syntax'
& $python -m compileall -q server.py terminal_manager.py message_store.py scripts/check_runtime.py

Write-Host '3/4 Backend and static asset smoke tests'
& $python scripts/check_runtime.py

Write-Host '4/4 PWA configuration'
& $nodePath scripts/check_pwa.js

Write-Host 'All checks passed.' -ForegroundColor Green
