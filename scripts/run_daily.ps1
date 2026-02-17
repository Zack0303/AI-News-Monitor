param(
    [ValidateSet("heuristic", "codex")]
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

if ($Mode -eq "heuristic") {
    $argsList += "--no-llm"
}
else {
    if (-not $env:OPENAI_API_KEY) {
        throw "Mode=codex requires OPENAI_API_KEY in environment."
    }
    if (-not $env:OPENAI_MODEL) {
        $env:OPENAI_MODEL = "gpt-5-codex"
    }
}

if ($SendEmail) {
    $argsList += "--send-email"
}

Write-Host "Running daily digest..."
Write-Host "Mode: $Mode, TopK: $TopK, SendEmail: $SendEmail"
python @argsList
