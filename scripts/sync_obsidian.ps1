param(
    [string]$VaultPath,
    [string]$SubFolder = "90-AI-News-Monitor"
)

$ErrorActionPreference = "Stop"

$ProjectRoot = Split-Path -Parent $PSScriptRoot
$OutputsDir = Join-Path $ProjectRoot "outputs"

if (!(Test-Path $OutputsDir)) {
    throw "outputs folder not found: $OutputsDir"
}

if (-not $VaultPath) {
    $VaultPath = $env:OBSIDIAN_VAULT_PATH
}

if (-not $VaultPath) {
    throw "VaultPath missing. Pass -VaultPath or set OBSIDIAN_VAULT_PATH."
}

if (!(Test-Path $VaultPath)) {
    throw "Vault path does not exist: $VaultPath"
}

$TargetDir = Join-Path $VaultPath $SubFolder
New-Item -ItemType Directory -Path $TargetDir -Force | Out-Null

$DailyDir = Join-Path $TargetDir "Daily"
$AgentDir = Join-Path $TargetDir "Agent"
$DataDir = Join-Path $TargetDir "Data"
@($DailyDir, $AgentDir, $DataDir) | ForEach-Object {
    New-Item -ItemType Directory -Path $_ -Force | Out-Null
}

$latestJson = Get-ChildItem -Path $OutputsDir -Filter "digest_*.json" | Sort-Object LastWriteTime | Select-Object -Last 1
$latestMd = Get-ChildItem -Path $OutputsDir -Filter "digest_*.md" | Sort-Object LastWriteTime | Select-Object -Last 1
$latestAgentJson = Get-ChildItem -Path $OutputsDir -Filter "agent_report_*.json" | Sort-Object LastWriteTime | Select-Object -Last 1
$latestAgentMd = Get-ChildItem -Path $OutputsDir -Filter "agent_report_*.md" | Sort-Object LastWriteTime | Select-Object -Last 1
$latestHtml = Get-ChildItem -Path $OutputsDir -Filter "latest_digest.html" | Select-Object -First 1

if (-not $latestJson -or -not $latestMd) {
    throw "No digest outputs found. Run daily job first."
}

Copy-Item $latestMd.FullName -Destination (Join-Path $DailyDir $latestMd.Name) -Force
Copy-Item $latestJson.FullName -Destination (Join-Path $DataDir $latestJson.Name) -Force

if ($latestHtml) {
    Copy-Item $latestHtml.FullName -Destination (Join-Path $DataDir $latestHtml.Name) -Force
}

if ($latestAgentMd) {
    Copy-Item $latestAgentMd.FullName -Destination (Join-Path $AgentDir $latestAgentMd.Name) -Force
}
if ($latestAgentJson) {
    Copy-Item $latestAgentJson.FullName -Destination (Join-Path $DataDir $latestAgentJson.Name) -Force
}

$latestNote = Join-Path $TargetDir "LATEST.md"
$htmlName = if ($latestHtml) { $latestHtml.Name } else { "not rendered yet" }
$agentMdLink = if ($latestAgentMd) { "[[$($latestAgentMd.BaseName)]]" } else { "not available yet" }
$agentJsonName = if ($latestAgentJson) { $latestAgentJson.Name } else { "not available yet" }
$content = @"
# AI News Monitor - Latest

- Daily Markdown: [[$($latestMd.BaseName)]]
- Daily JSON: $($latestJson.Name)
- Agent Markdown: $agentMdLink
- Agent JSON: $agentJsonName
- HTML Dashboard: $htmlName

## Folder Layout
- Daily: `Daily/`
- Agent: `Agent/`
- Data: `Data/`

Updated At: $(Get-Date -Format "yyyy-MM-dd HH:mm:ss")
"@
Set-Content -Path $latestNote -Encoding UTF8 -Value $content

Write-Host "[OK] Synced to Obsidian root: $TargetDir"
Write-Host "     Daily -> $DailyDir"
Write-Host "     Agent -> $AgentDir"
Write-Host "     Data  -> $DataDir"
