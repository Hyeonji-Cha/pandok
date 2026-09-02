$ErrorActionPreference = "Stop"

# Resolve the repository root from this script's location so it works on any machine.
$Repo = (Resolve-Path (Join-Path $PSScriptRoot "..\..")).Path
$Target = Join-Path $Repo "kingcharles_turkiye_gateway"

if (-not (Test-Path (Join-Path $Repo ".git"))) {
    throw "PANDOK repo not found: $Repo"
}

Set-Location $Repo

Write-Host "=== REPO STATUS ==="
git status --short

Write-Host "`n=== OUR FOLDER ==="
if (Test-Path $Target) {
    Get-ChildItem $Target -Recurse -File |
        ForEach-Object { $_.FullName.Substring($Repo.Length + 1) }
} else {
    Write-Host "NOT_INSTALLED"
}

Write-Host "`n=== EXISTING PANDOK FILE CHANGES ==="
$Other = @(git status --short | Where-Object {
    $_ -notmatch 'kingcharles_turkiye_gateway'
})

if ($Other.Count -eq 0) {
    Write-Host "EXISTING_REPO_FILES_UNCHANGED=True"
} else {
    Write-Host "EXISTING_REPO_FILES_UNCHANGED=False"
    $Other
}
