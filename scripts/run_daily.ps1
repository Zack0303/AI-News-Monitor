param(
    [ValidateSet("heuristic", "llm")]
    [string]$Mode = "heuristic",
    [int]$TopK = 12,
    [switch]$SendEmail
)

$ErrorActionPreference = "Stop"

$ProjectRoot = Split-Path -Parent $PSScriptRoot
$MainScript = Join-Path $ProjectRoot "phase1_rss\main.py"

if (!(Test-Path $MainScript)) {
    throw "Cannot find main script: $MainScript"
}

$argsList = @($MainScript, "--top-k", "$TopK")

Write-Host "Updating preference profile..."
python .\scripts\update_preference_profile.py

if ($Mode -eq "heuristic") {
    $argsList += "--no-llm"
}
else {
    if (-not $env:GEMINI_API_KEY) {
        throw "Mode=llm requires GEMINI_API_KEY in environment."
    }
    if (-not $env:GEMINI_MODEL) {
        $env:GEMINI_MODEL = "gemini-2.0-flash"
    }
}

if ($SendEmail) {
    $argsList += "--send-email"
}

Write-Host "Running daily digest..."
Write-Host "Mode: $Mode, TopK: $TopK, SendEmail: $SendEmail"
python @argsList
