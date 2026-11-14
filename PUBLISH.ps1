$ErrorActionPreference = 'Stop'
Set-Location (Split-Path -Parent $MyInvocation.MyCommand.Path)
if (-not (Get-Command git -ErrorAction SilentlyContinue)) { throw 'Git is required' }
if (-not (Get-Command gh -ErrorAction SilentlyContinue)) { throw 'GitHub CLI is required' }
py -3 -B scripts\verify_package_v18.py --require-release
if ($LASTEXITCODE -ne 0) { throw 'Publication HOLD. Resolve the v0.18 platform gates first.' }
throw 'No automatic publication. Review the exact commit, visibility, and artifact hashes with the repository owner before creating or pushing a remote.'
