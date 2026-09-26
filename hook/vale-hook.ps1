# Claude Code PostToolUse hook. Reads the hook payload on stdin and lints what
# Claude just wrote with the NoSlop styles. Exit 2 sends the hits back to Claude.
#
# Prose (.md/.txt under a folder named -ProseDir): lints the whole file.
# Code and HTML: lints only the text Claude wrote (Edit new_string, MultiEdit
# edits, or Write content), so old text elsewhere in the file doesn't block an edit.
#
# -ProseDir (or $env:SLOP_LINTER_PROSE_DIR): folder name that marks prose.
#   Default "Writing". Use "*" to lint every .md/.txt file.
# -ProseSkip (or $env:SLOP_LINTER_PROSE_SKIP): comma-separated subfolder names
#   directly under -ProseDir to leave alone (any depth when -ProseDir is "*").
#   Default "reference,_archive". Pass -ProseSkip '' to skip nothing.
# -Vale (or $env:VALE_BIN): path to vale.exe when Vale isn't on PATH.
# -LocalConfig (or $env:SLOP_LINTER_LOCAL_CONFIG): a config path relative to a
#   project root, such as .devkit\kit\vale.ini. If a folder above the edited file
#   has it, that config is used instead of this repo's, so per-project settings
#   and vocabularies apply.

param(
    [string]$ProseDir = $(if ($env:SLOP_LINTER_PROSE_DIR) { $env:SLOP_LINTER_PROSE_DIR } else { 'Writing' }),
    [string]$ProseSkip = $(if ($env:SLOP_LINTER_PROSE_SKIP) { $env:SLOP_LINTER_PROSE_SKIP } else { 'reference,_archive' }),
    [string]$Vale = $(if ($env:VALE_BIN) { $env:VALE_BIN } else { 'vale' }),
    [string]$LocalConfig = $(if ($env:SLOP_LINTER_LOCAL_CONFIG) { $env:SLOP_LINTER_LOCAL_CONFIG } else { '' })
)

$ErrorActionPreference = 'Stop'

# PowerShell 5.1 reads stdin in the OEM code page, which mangles non-ASCII paths.
[Console]::InputEncoding = New-Object Text.UTF8Encoding $false
try { $payload = [Console]::In.ReadToEnd() | ConvertFrom-Json } catch { exit 0 }
$path = $payload.tool_input.file_path
if (-not $path) { exit 0 }

$config = Join-Path (Split-Path $PSScriptRoot -Parent) '.vale.ini'
if ($LocalConfig) {
    $dir = Split-Path -Parent ([IO.Path]::GetFullPath($path))
    while ($dir) {
        $candidate = Join-Path $dir $LocalConfig
        if (Test-Path -LiteralPath $candidate) { $config = $candidate; break }
        $parent = Split-Path -Parent $dir
        if ($parent -eq $dir) { break }
        $dir = $parent
    }
}
$codeExt = '\.(py|js|jsx|mjs|cjs|ts|tsx|mts|cts|ps1|psm1|go|rs|c|cpp|h|cs|java|rb|lua|php|html)$'
$skipDirs = '[\\/](\.git|\.devkit|node_modules|githubs|dist|build|vendor|\.venv|venv|__pycache__)[\\/]'

function Send-Hits($label, $hits) {
    [Console]::Error.WriteLine("Vale flagged $label. Rewrite each flagged sentence; don't swap in a synonym. Save again when done.")
    $hits | ForEach-Object { [Console]::Error.WriteLine($_) }
    exit 2
}

function Test-Prose($p) {
    if ($p -notmatch '\.(md|txt)$') { return $false }
    $skip = @($ProseSkip -split ',' | ForEach-Object { $_.Trim() } | Where-Object { $_ })
    if ($ProseDir -eq '*') {
        foreach ($s in $skip) { if ($p -match ('[\\/]' + [regex]::Escape($s) + '[\\/]')) { return $false } }
        return $true
    }
    $dir = '[\\/]' + [regex]::Escape($ProseDir) + '[\\/]'
    if ($p -notmatch $dir) { return $false }
    foreach ($s in $skip) { if ($p -match ($dir + [regex]::Escape($s) + '[\\/]')) { return $false } }
    return $true
}

$isProse = (Test-Prose $path) -and ($path -notmatch $skipDirs)
$isCode = ($path -match $codeExt) -and ($path -notmatch $skipDirs)
if (-not $isProse -and -not $isCode) { exit 0 }

if (-not (Get-Command $Vale -ErrorAction SilentlyContinue)) {
    [Console]::Error.WriteLine("vale-hook: Vale not found at '$Vale'. Install it, or pass -Vale with the path to vale.exe.")
    exit 1
}

if ($isProse) {
    if (-not (Test-Path -LiteralPath $path)) { exit 0 }
    # Only rules with a single safe fix carry an action (curly quotes today).
    & $Vale "--config=$config" --minAlertLevel=warning fix --apply $path | Out-Null
    $hits = & $Vale "--config=$config" --minAlertLevel=warning --output=line $path
    if ($hits) { Send-Hits $path $hits }
    exit 0
}

if ($isCode) {
    $ti = $payload.tool_input
    $parts = @()
    if ($ti.new_string) { $parts += $ti.new_string }
    if ($ti.edits) { foreach ($e in $ti.edits) { if ($e.new_string) { $parts += $e.new_string } } }
    if ($ti.content) { $parts += $ti.content }
    if ($parts.Count -eq 0) { exit 0 }

    # Temp file with the same extension so Vale picks the right comment grammar.
    # UTF-8 without BOM so em dashes survive Windows PowerShell 5.1.
    # Vale 3.22 skips .mjs/.cjs/.mts/.cts even with [formats]; lint them as .js/.ts.
    $ext = [IO.Path]::GetExtension($path).ToLower()
    $ext = @{ '.mjs' = '.js'; '.cjs' = '.js'; '.mts' = '.ts'; '.cts' = '.ts' }[$ext], $ext | Where-Object { $_ } | Select-Object -First 1
    $tmp = Join-Path ([IO.Path]::GetTempPath()) ("vale-hook-" + [guid]::NewGuid().ToString('N') + $ext)
    [IO.File]::WriteAllText($tmp, ($parts -join "`n"), (New-Object Text.UTF8Encoding $false))
    try {
        $hits = & $Vale "--config=$config" --minAlertLevel=warning --output=line $tmp
    } finally {
        Remove-Item -LiteralPath $tmp -ErrorAction SilentlyContinue
    }
    if ($hits) {
        $hits = $hits | ForEach-Object { $_.Replace($tmp, "(new text in $path)") }
        Send-Hits "comments in the text just written to $path (line numbers are relative to that text)" $hits
    }
    exit 0
}

exit 0
