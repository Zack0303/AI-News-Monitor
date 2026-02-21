param(
    [switch]$Preview,
    [int]$TopK = 12
)

$ErrorActionPreference = "Stop"
$ProjectRoot = Split-Path -Parent $PSScriptRoot
Set-Location $ProjectRoot

Write-Host "[1/3] Build static site..." -ForegroundColor Cyan
python .\scripts\build_static_site.py --top-k $TopK

if ($Preview) {
    Write-Host "[2/3] Preview on http://localhost:8080 (Ctrl+C to stop)" -ForegroundColor Green
    Set-Location .\site
    python -m http.server 8080
    Set-Location $ProjectRoot
}

Write-Host "[3/3] Commit and push site..." -ForegroundColor Cyan
git add site
git commit -m "Publish static site $(Get-Date -Format 'yyyy-MM-dd HH:mm')" 2>$null
if ($LASTEXITCODE -ne 0) {
    Write-Host "No new site changes to commit." -ForegroundColor Yellow
} else {
    $CurrentBranch = (git rev-parse --abbrev-ref HEAD).Trim()
    git push origin $CurrentBranch
}

Write-Host "Done. Check GitHub Actions deployment." -ForegroundColor Green
