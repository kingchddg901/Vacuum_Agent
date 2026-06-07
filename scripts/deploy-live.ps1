# =============================================================================
# deploy-live.ps1 -- hand-deploy the CURRENT working tree to the live HA for TESTING.
# =============================================================================
#
# This is the test-iteration path, NOT a release. You cannot iterate-test through
# HACS (HACS is a publish), so the live-path hand-copy is how a branch is validated
# before it is merged + released.
#
# It must be CONSISTENT: it always does a COMPLETE overwrite of the integration
# from the repo (every file, minus __pycache__/*.pyc) plus both card-bundle
# locations. The old "drift" problem came from partial / stale manual edits -- a
# full deterministic copy from the repo cannot drift, and HACS overwrites it on
# its next real update anyway.
#
# Usage (PowerShell):   scripts\deploy-live.ps1            # build the card, then copy
#                       scripts\deploy-live.ps1 -SkipBuild # copy the current bundle as-is
#
# After it runs: RESTART Home Assistant + hard-refresh the browser (Ctrl+Shift+R).
# =============================================================================

param([switch]$SkipBuild)

$ErrorActionPreference = "Stop"

$repo     = Split-Path -Parent $PSScriptRoot        # scripts/ -> repo root
$src      = Join-Path $repo "custom_components\eufy_vacuum"
$liveRoot = "Z:\"                                    # mapped to \\192.168.4.104\config
$dst      = Join-Path $liveRoot "custom_components\eufy_vacuum"
$wwwCard  = Join-Path $liveRoot "www\eufy-vacuum-command-center.js"
$bundle   = Join-Path $src "frontend\eufy-vacuum-command-center.js"

if (-not (Test-Path $liveRoot)) {
    throw "Live config drive Z:\ is not mapped (\\192.168.4.104\config). Map it, then retry."
}
if (-not (Test-Path $dst)) {
    throw "Live integration not found at $dst -- refusing to create a copy at the wrong path."
}
if (-not (Test-Path $src)) {
    throw "Repo integration not found at $src."
}

if (-not $SkipBuild) {
    Write-Host "[1/3] Building card bundle (npm run build:deploy)..."
    Push-Location $repo
    try { npm run build:deploy } finally { Pop-Location }
}
else {
    Write-Host "[1/3] Skipping card build (-SkipBuild)."
}

Write-Host "[2/3] Copying integration to $dst (excluding __pycache__/*.pyc)..."
& robocopy $src $dst /E /XD __pycache__ /XF *.pyc /NFL /NDL /NJH /NJS /R:1 /W:1 | Out-Null
$rc = $LASTEXITCODE
if ($rc -ge 8) { throw "robocopy failed (exit $rc)." }   # robocopy: <8 == success

Write-Host "[3/3] Refreshing the www card bundle (served as /local/)..."
Copy-Item $bundle $wwwCard -Force

Write-Host ""
Write-Host "DEPLOYED to live (robocopy rc=$rc). This is a TEST copy, NOT a release."
Write-Host "  - integration: $dst"
Write-Host "  - card:        frontend\ + $wwwCard"
Write-Host ""
Write-Host "NEXT: restart Home Assistant, then hard-refresh the dashboard (Ctrl+Shift+R)."
exit 0
