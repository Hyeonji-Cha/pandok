$ErrorActionPreference = "Stop"

$Repo = "$env:USERPROFILE\Desktop\pandok"
$TargetRel = "kingcharles_turkiye_gateway"
$Target = Join-Path $Repo $TargetRel

Set-Location $Repo

$Tracked = @(git ls-files -- $TargetRel)
if ($Tracked.Count -gt 0) {
    throw "REFUSING: the folder already contains tracked files. Use git revert/restore workflow instead."
}

if (Test-Path $Target) {
    Remove-Item $Target -Recurse -Force
    Write-Host "REMOVED_UNTRACKED_FOLDER=$TargetRel"
} else {
    Write-Host "NOTHING_TO_REMOVE"
}

git status --short
