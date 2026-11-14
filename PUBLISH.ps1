$ErrorActionPreference = 'Stop'
$repo = 'jacksonjp0311-gif/NOMAD'
Set-Location (Split-Path -Parent $MyInvocation.MyCommand.Path)
if (-not (Get-Command git -ErrorAction SilentlyContinue)) { throw 'Git is required' }
if (-not (Get-Command gh -ErrorAction SilentlyContinue)) { throw 'GitHub CLI is required' }
py -3 scripts\verify_package_v17.py --tests --security --smoke
if ($LASTEXITCODE -ne 0) { throw 'NOMAD v0.17 protection, recovery, manifest or regression gate failed' }
if (-not (Test-Path .git)) { git init -b main }
git add .
git diff --cached --quiet
if ($LASTEXITCODE -ne 0) { git commit -m 'NOMAD v0.17.0: SECURITY & RECOVERY, fail-closed execution, external-effect ledger' }
git branch -M main
$origin = git remote get-url origin 2>$null
if ($LASTEXITCODE -ne 0) {
    gh auth status
    if ($LASTEXITCODE -ne 0) { throw 'GitHub authentication required' }
    gh repo create $repo --public --source . --remote origin --push --description 'NOMAD: Bitwork-derived coding intelligence with independent WITNESS and restartable missions'
} else {
    git push -u origin main
}
if ($LASTEXITCODE -ne 0) { throw 'GitHub publish failed' }
Write-Host "Published: https://github.com/$repo"
