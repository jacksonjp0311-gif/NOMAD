[CmdletBinding()]
param(
    [ValidateSet('setup','doctor','verify','trusted-demo','runtime-smoke','dry-run','isolated-demo','status','recover','run')]
    [string]$Action = 'doctor',
    [string]$Image,
    [string]$Source,
    [string]$MissionRoot,
    [string]$Config
)
$ErrorActionPreference = 'Stop'
$repoRoot = $PSScriptRoot
$venvPython = Join-Path $repoRoot '.venv\Scripts\python.exe'
Push-Location -LiteralPath $repoRoot
try {
    if ($Action -eq 'setup') {
        if (-not (Test-Path -LiteralPath $venvPython)) {
            & py -3 -m venv (Join-Path $repoRoot '.venv')
            if ($LASTEXITCODE -ne 0) { throw 'Python 3.11+ venv setup failed' }
        }
        # Source-linked, offline installation. No downloaded installers/dependencies.
        $site = & $venvPython -c 'import site; print(site.getsitepackages()[-1])'
        if ($LASTEXITCODE -ne 0) { throw 'Could not locate local virtual environment' }
        [IO.File]::WriteAllText((Join-Path $site 'nomad_source.pth'), $repoRoot + [Environment]::NewLine, [Text.UTF8Encoding]::new($false))
        & $venvPython -B -c 'import sys,nomad; assert sys.version_info >= (3,11); print("NOMAD",nomad.__version__)'
        if ($LASTEXITCODE -ne 0) { throw 'NOMAD source installation verification failed' }
        $Action = 'doctor'
    }
    if (-not (Test-Path -LiteralPath $venvPython)) {
        throw 'Run .\NOMAD.ps1 -Action setup first, or use py -3 -m nomad.platform_cli directly.'
    }
    if ($Action -eq 'verify') {
        & $venvPython -B scripts\verify_package_v18.py
    } else {
        $arguments = @('-B','-m','nomad.platform_cli')
        if ($Config) { $arguments += @('--config',$Config) }
        if ($Image) { $arguments += @('--image',$Image) }
        $arguments += $Action
        if ($Source) { $arguments += @('--source',$Source) }
        if ($MissionRoot) { $arguments += @('--root',$MissionRoot) }
        & $venvPython @arguments
    }
    exit $LASTEXITCODE
} finally { Pop-Location }
