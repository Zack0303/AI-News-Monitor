param(
    [string]$SiteDir = "site"
)

$ErrorActionPreference = "Stop"

$ProjectRoot = Split-Path -Parent $PSScriptRoot
$ResolvedSiteDir = Join-Path $ProjectRoot $SiteDir

if (!(Test-Path $ResolvedSiteDir)) {
    throw "Site directory not found: $ResolvedSiteDir"
}

$errors = New-Object System.Collections.Generic.List[string]

function Assert-True {
    param(
        [bool]$Condition,
        [string]$Message
    )
    if (-not $Condition) {
        $errors.Add($Message)
    }
}

$requiredFiles = @(
    "index.html",
    "history.html",
    "assets/style.css",
    "assets/app.js",
    "data/latest.json"
)

foreach ($f in $requiredFiles) {
    $p = Join-Path $ResolvedSiteDir $f
    Assert-True (Test-Path $p) "Missing required file: $f"
}

$indexPath = Join-Path $ResolvedSiteDir "index.html"
if (Test-Path $indexPath) {
    $indexContent = Get-Content $indexPath -Raw -Encoding UTF8
    Assert-True ($indexContent -match "class=""panel trust-panel""") "index.html missing trust panel"
    Assert-True ($indexContent -match "class=""focus-grid""") "index.html missing focus grid"
    Assert-True ($indexContent -match "id=""result-count""") "index.html missing result counter"
}

$latestJsonPath = Join-Path $ResolvedSiteDir "data/latest.json"
if (Test-Path $latestJsonPath) {
    try {
        $latest = Get-Content $latestJsonPath -Raw -Encoding UTF8 | ConvertFrom-Json
        Assert-True ($null -ne $latest.run_meta) "latest.json missing run_meta"
        Assert-True ($latest.run_meta.fallback_reason -eq "") "latest.json fallback_reason should be empty in public data"
        Assert-True ($latest.run_meta.fallback_reason_public -eq "redacted") "latest.json fallback_reason_public should be redacted"
        Assert-True ($null -ne $latest.items -and $latest.items.Count -ge 1) "latest.json should contain at least one item"
    }
    catch {
        $errors.Add("latest.json is not valid JSON: $($_.Exception.Message)")
    }
}

if ($errors.Count -gt 0) {
    Write-Host "[FAIL] Post publish checks failed:" -ForegroundColor Red
    foreach ($err in $errors) {
        Write-Host " - $err" -ForegroundColor Red
    }
    exit 1
}

Write-Host "[PASS] Post publish checks passed." -ForegroundColor Green
Write-Host "       Site dir: $ResolvedSiteDir"
