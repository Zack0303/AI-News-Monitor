param(
    [ValidateSet("heuristic", "llm")]
    [string]$Mode = "llm",
    [int]$TopK = 12,
    [int]$MaxRssPerSource = 10,
    [int]$GitHubLimit = 10,
    [switch]$RunAgent = $true,
    [switch]$UseAgentLlm = $false,
    [string]$VaultPath = "E:\Career\Career",
    [switch]$SkipSync = $false
)

$ErrorActionPreference = "Stop"

$ProjectRoot = Split-Path -Parent $PSScriptRoot
Set-Location $ProjectRoot

Write-Host "[1/4] Running phase1 digest..."
$phase1Args = @(
    ".\phase1_rss\main.py",
    "--top-k", "$TopK",
    "--max-rss-per-source", "$MaxRssPerSource",
    "--github-limit", "$GitHubLimit"
)
if ($Mode -eq "heuristic") {
    $phase1Args += "--no-llm"
}
python @phase1Args

Write-Host "[2/4] Rendering HTML dashboard..."
python .\scripts\render_latest.py

if ($RunAgent) {
    Write-Host "[3/4] Running phase2 agent report..."
    $agentArgs = @(".\phase2_agent\agent.py")
    if ($UseAgentLlm) {
        $agentArgs += "--use-llm"
    }
    python @agentArgs
}
else {
    Write-Host "[3/4] Skipped phase2 agent."
}

if (-not $SkipSync) {
    Write-Host "[4/4] Syncing to Obsidian..."
    .\scripts\sync_obsidian.ps1 -VaultPath $VaultPath
}
else {
    Write-Host "[4/4] Skipped Obsidian sync."
}

Write-Host "[DONE] Full pipeline completed."
