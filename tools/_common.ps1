# IslamicAI Fix Toolkit - shared helpers (ASCII only, do not add non-ASCII here)
$ErrorActionPreference = "Stop"

function Write-Step  { param($m) Write-Host "`n=== $m ===" -ForegroundColor Cyan }
function Write-Ok    { param($m) Write-Host "  [ OK ] $m" -ForegroundColor Green }
function Write-Warn2 { param($m) Write-Host "  [WARN] $m" -ForegroundColor Yellow }
function Write-Err2  { param($m) Write-Host "  [FAIL] $m" -ForegroundColor Red }
function Write-Info  { param($m) Write-Host "  [ .. ] $m" -ForegroundColor Gray }
function Write-Dry   { param($m) Write-Host "  [DRY ] $m" -ForegroundColor Magenta }

function Get-FullPath {
    param([Parameter(Mandatory)][string]$Path)
    return [System.IO.Path]::GetFullPath(
        [System.IO.Path]::Combine((Get-Location).Path, $Path))
}

# Read a file as UTF-8 no matter what the console codepage is.
function Read-Utf8 {
    param([Parameter(Mandatory)][string]$Path)
    return [System.IO.File]::ReadAllText((Get-FullPath $Path),
        (New-Object System.Text.UTF8Encoding($false)))
}

# Write UTF-8 without BOM. Correct for .py files.
function Write-Utf8NoBom {
    param(
        [Parameter(Mandatory)][string]$Path,
        [Parameter(Mandatory)][AllowEmptyString()][string]$Content
    )
    $dir = Split-Path -Parent $Path
    if ($dir -and -not (Test-Path -LiteralPath $dir)) {
        New-Item -ItemType Directory -Force -Path $dir | Out-Null
    }
    [System.IO.File]::WriteAllText((Get-FullPath $Path), $Content,
        (New-Object System.Text.UTF8Encoding($false)))
}

function Assert-RepoRoot {
    if (-not (Test-Path -LiteralPath ".git")) {
        throw "Not a git repository root. Run this from the islamicai project folder."
    }
    if (-not (Test-Path -LiteralPath "pyproject.toml")) {
        throw "pyproject.toml not found. Are you in the project root?"
    }
    Write-Ok ("Repo root: " + (Get-Location).Path)
}

function Test-GitClean {
    return [string]::IsNullOrWhiteSpace((git status --porcelain))
}

function Remove-FromGitIndex {
    param([Parameter(Mandatory)][string]$PathSpec, [switch]$DryRun)
    $tracked = git ls-files -- $PathSpec
    if ([string]::IsNullOrWhiteSpace($tracked)) {
        Write-Info "not tracked: $PathSpec"
        return 0
    }
    $count = ($tracked -split "`n" | Where-Object { $_ -ne "" }).Count
    if ($DryRun) { Write-Dry "would untrack $count file(s): $PathSpec"; return $count }
    git rm --cached -r --quiet -- $PathSpec 2>$null | Out-Null
    Write-Ok "untracked $count file(s), kept on disk: $PathSpec"
    return $count
}

function New-StrongPassword {
    param([int]$Length = 32)
    $bytes = New-Object byte[] ($Length)
    $rng = [System.Security.Cryptography.RandomNumberGenerator]::Create()
    $rng.GetBytes($bytes); $rng.Dispose()
    $chars = 'abcdefghijkmnopqrstuvwxyzABCDEFGHJKLMNPQRSTUVWXYZ23456789'
    return (-join ($bytes | ForEach-Object { $chars[$_ % $chars.Length] }))
}

function Get-Stamp { return (Get-Date).ToString("yyyyMMdd-HHmmss") }

function Get-Python {
    $p = Get-Command python -ErrorAction SilentlyContinue
    if (-not $p) { $p = Get-Command python3 -ErrorAction SilentlyContinue }
    if (-not $p) { $p = Get-Command py -ErrorAction SilentlyContinue }
    return $p
}
