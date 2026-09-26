<#
Batch slop-QA over a tree. Lints code comments and prose Markdown with the
NoSlop/NoSlopCode Vale styles, then prints a ranked report.

Two things a plain `vale <dir>` gets wrong that this handles:
  - Vale 3.22 silently skips .mjs/.cjs/.mts/.cts. This pipes them through
    stdin as .js/.ts so they get linted.
  - It ranks hits by rule and by file so you triage instead of scrolling.

Inside a git repo it lints only files git tracks, so local notes, captures,
and ignored data stay out of the counts. -All lints every file in the tree
instead, tracked or not. Outside a git repo it always walks the tree.

Excludes build/vendor/VCS dirs either way. It does not exclude data/ or any
content dir; pass those with -Exclude per run when you don't want them.

  .\run-qa.ps1 -Path C:\path\to\project
  .\run-qa.ps1 -Path C:\path\to\project -All
  .\run-qa.ps1 -Path C:\path\to\project -Exclude data,chrome,firefox
  .\run-qa.ps1 -Path C:\path\to\project -Level suggestion -OutFile hits.tsv
#>
param(
  [Parameter(Mandatory)][string]$Path,
  [string[]]$Exclude = @(),
  [ValidateSet("suggestion","warning","error")][string]$Level = "warning",
  [string]$Config = "$PSScriptRoot\.vale.ini",
  [int]$Top = 15,
  [string]$OutFile,
  [switch]$All
)

$ErrorActionPreference = "Stop"
if (-not (Get-Command vale -ErrorAction SilentlyContinue)) { throw "vale not on PATH." }
if (-not (Test-Path $Config)) { throw "Config not found: $Config" }

$skipDirs = @(
  "node_modules",".git","dist","build","__pycache__",".venv","venv",
  ".wrangler",".next","vendor",".svelte-kit",".pytest_cache",".mypy_cache"
) + $Exclude

$prose   = ".md",".txt",".html"
$code    = ".py",".js",".jsx",".ts",".tsx",".ps1",".psm1",".go",".rs",".rb",".lua",".php"
$stdin   = @{ ".mjs"="js"; ".cjs"="js"; ".mts"="ts"; ".cts"="ts" }
$allExt  = $prose + $code + ($stdin.Keys)

$Path = (Resolve-Path -LiteralPath $Path).ProviderPath.TrimEnd('\')
$tracked = $false
if (-not $All -and (Get-Command git -ErrorAction SilentlyContinue)) {
  $ErrorActionPreference = "Continue"
  $inRepo = (git -C $Path rev-parse --is-inside-work-tree 2>$null) -eq "true"
  if ($inRepo) {
    # Windows PowerShell 5.1 decodes native output in the OEM code page, which
    # mangles non-ASCII paths. quotepath=off stops git escaping them as octal.
    $prevEnc = [Console]::OutputEncoding
    [Console]::OutputEncoding = New-Object Text.UTF8Encoding $false
    $list = @(git -C $Path -c core.quotepath=off ls-files 2>$null)
    [Console]::OutputEncoding = $prevEnc
    $tracked = $LASTEXITCODE -eq 0
  }
  $ErrorActionPreference = "Stop"
}
$candidates = if ($tracked) {
  # A tracked file deleted from the working tree has nothing to lint.
  $list | ForEach-Object { Join-Path $Path $_ } | Where-Object { Test-Path -LiteralPath $_ -PathType Leaf } | ForEach-Object { Get-Item -LiteralPath $_ }
} else {
  Get-ChildItem -Path $Path -Recurse -File
}
$files = @($candidates | Where-Object {
  $allExt -contains $_.Extension.ToLower() -and
  -not ($_.FullName -split '[\\/]' | Where-Object { $skipDirs -contains $_ })
})

$rows = New-Object System.Collections.Generic.List[object]
$stdinCount = 0

foreach ($f in $files) {
  $ext = $f.Extension.ToLower()
  # 'Continue' so Vale's stderr is captured instead of terminating the script
  # (Windows PowerShell 5.1) or vanishing (7.x). Exit 2 means Vale itself failed.
  $ErrorActionPreference = "Continue"
  if ($stdin.ContainsKey($ext)) {
    $out = Get-Content -Raw -Encoding UTF8 -LiteralPath $f.FullName | vale --config="$Config" --ext=".$($stdin[$ext])" --minAlertLevel=$Level --output=JSON 2>&1
    $stdinCount++
  } else {
    $out = vale --config="$Config" --minAlertLevel=$Level --output=JSON $f.FullName 2>&1
  }
  $code = $LASTEXITCODE
  $ErrorActionPreference = "Stop"
  $errs = @($out | Where-Object { $_ -is [System.Management.Automation.ErrorRecord] })
  if ($code -ge 2) { throw "vale failed on $($f.FullName): $($errs -join ' ')" }
  $json = ($out | Where-Object { $_ -isnot [System.Management.Automation.ErrorRecord] }) -join "`n"
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
$scope = if ($tracked) { "git-tracked only; -All for every file" } else { "every file in the tree" }
Write-Host "Scanned $($files.Count) files, $scope ($stdinCount via stdin: .mjs/.cjs/.mts/.cts)"
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
