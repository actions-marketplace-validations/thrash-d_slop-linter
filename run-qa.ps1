<#
Batch slop-QA over a tree. Lints code comments and prose Markdown with the
NoSlop/NoSlopCode Vale styles, then prints a ranked report.

Two things a plain `vale <dir>` gets wrong that this handles:
  - Vale 3.22 silently skips .mjs/.cjs/.mts/.cts. This pipes them through
    stdin as .js/.ts so they get linted.
  - It ranks hits by rule and by file so you triage instead of scrolling.

Excludes build/vendor/VCS dirs by default. It does not exclude data/ or any
content dir; pass those with -Exclude per run when you don't want them.

  .\run-qa.ps1 -Path C:\path\to\project
  .\run-qa.ps1 -Path C:\path\to\project -Exclude data,chrome,firefox
  .\run-qa.ps1 -Path C:\path\to\project -Level suggestion -OutFile hits.tsv
#>
param(
  [Parameter(Mandatory)][string]$Path,
  [string[]]$Exclude = @(),
  [ValidateSet("suggestion","warning","error")][string]$Level = "warning",
  [string]$Config = "$PSScriptRoot\.vale.ini",
  [int]$Top = 15,
  [string]$OutFile
)

$ErrorActionPreference = "Stop"
if (-not (Get-Command vale -ErrorAction SilentlyContinue)) { throw "vale not on PATH." }
if (-not (Test-Path $Config)) { throw "Config not found: $Config" }

$skipDirs = @(
  "node_modules",".git","dist","build","__pycache__",".venv","venv",
  ".wrangler",".next","vendor",".svelte-kit",".pytest_cache",".mypy_cache"
) + $Exclude

$prose   = ".md",".txt"
$code    = ".py",".js",".jsx",".ts",".tsx",".ps1",".psm1",".go",".rs",".rb",".lua",".php"
$stdin   = @{ ".mjs"="js"; ".cjs"="js"; ".mts"="ts"; ".cts"="ts" }
$allExt  = $prose + $code + ($stdin.Keys)

$files = Get-ChildItem -Path $Path -Recurse -File | Where-Object {
  $allExt -contains $_.Extension.ToLower() -and
  -not ($_.FullName -split '[\\/]' | Where-Object { $skipDirs -contains $_ })
}

$rows = New-Object System.Collections.Generic.List[object]
$stdinCount = 0

foreach ($f in $files) {
  $ext = $f.Extension.ToLower()
  if ($stdin.ContainsKey($ext)) {
    $json = Get-Content -Raw -LiteralPath $f.FullName | vale --config="$Config" --ext=".$($stdin[$ext])" --minAlertLevel=$Level --output=JSON 2>$null
    $stdinCount++
  } else {
    $json = vale --config="$Config" --minAlertLevel=$Level --output=JSON $f.FullName 2>$null
  }
  if (-not $json) { continue }
  try { $parsed = $json | ConvertFrom-Json } catch { continue }
  foreach ($prop in $parsed.PSObject.Properties) {
    foreach ($a in $prop.Value) {
      $rows.Add([pscustomobject]@{
        File = $f.FullName.Substring($Path.Length).TrimStart('\','/')
        Line = $a.Line; Rule = $a.Check; Severity = $a.Severity; Message = $a.Message
      })
    }
  }
}

Write-Host ""
Write-Host "Scanned $($files.Count) files ($stdinCount via stdin: .mjs/.cjs/.mts/.cts)"
Write-Host "Total hits (>= $Level): $($rows.Count)"
Write-Host ""
Write-Host "By rule:"
$rows | Group-Object Rule | Sort-Object Count -Descending |
  ForEach-Object { "{0,5}  {1}" -f $_.Count, $_.Name }
Write-Host ""
Write-Host "Worst $Top files:"
$rows | Group-Object File | Sort-Object Count -Descending | Select-Object -First $Top |
  ForEach-Object { "{0,5}  {1}" -f $_.Count, $_.Name }

if ($OutFile) {
  $rows | Sort-Object File, {[int]$_.Line} | Export-Csv -Path $OutFile -NoTypeInformation -Delimiter "`t"
  Write-Host ""
  Write-Host "Full detail written to $OutFile"
}
