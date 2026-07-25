<#
.SYNOPSIS
  Full backup before any change. Run this first.
#>
[CmdletBinding()]
param(
    [string]$BackupRoot = ".\_backup",
    [string]$PgContainer = "islamicai_postgres"
)
. "$PSScriptRoot\_common.ps1"
Assert-RepoRoot

$stamp = Get-Stamp
$dest  = Join-Path $BackupRoot $stamp
New-Item -ItemType Directory -Force -Path $dest | Out-Null
Write-Ok "Backup folder: $dest"

Write-Step "1/4  Git tag and branch"
$tag = "pre-fix-$stamp"
try { git tag -a $tag -m "Snapshot before fix toolkit" 2>$null | Out-Null; Write-Ok "tag: $tag" }
catch { Write-Warn2 "could not create tag" }
try { git branch "backup/pre-fix-$stamp" 2>$null | Out-Null; Write-Ok "branch: backup/pre-fix-$stamp" }
catch { Write-Warn2 "could not create branch" }
if (-not (Test-GitClean)) {
    Write-Warn2 "You have uncommitted changes. The tag does not capture them."
    Write-Warn2 "Recommended: git add -A ; git commit -m 'wip before fixes'"
}

Write-Step "2/4  Copy storage and .env"
foreach ($item in @("storage", ".env", ".env.bak")) {
    if (Test-Path -LiteralPath $item) {
        Copy-Item -LiteralPath $item -Destination $dest -Recurse -Force
        Write-Ok "copied: $item"
    } else { Write-Info "not present: $item" }
}

Write-Step "3/4  Database dump"
$docker = Get-Command docker -ErrorAction SilentlyContinue
if (-not $docker) {
    Write-Warn2 "docker not available - skipping DB dump. Take one manually."
} else {
    $running = docker ps --filter "name=$PgContainer" --format "{{.Names}}" 2>$null
    if ([string]::IsNullOrWhiteSpace($running)) {
        Write-Warn2 "container $PgContainer not running - skipping DB dump."
    } else {
        $dbUser = "islamicai"; $dbName = "islamicai"
        if (Test-Path .env) {
            $envTxt = Read-Utf8 ".env"
            if ($envTxt -match 'POSTGRES_USER=(.+)') { $dbUser = $Matches[1].Trim() }
            if ($envTxt -match 'POSTGRES_DB=(.+)')   { $dbName = $Matches[1].Trim() }
        }
        $dumpPath = Join-Path $dest "islamicai-$stamp.dump"
        Write-Info "running pg_dump on database $dbName ..."
        # Use cmd redirection to keep the binary stream intact.
        cmd /c "docker exec $PgContainer pg_dump -U $dbUser -d $dbName -Fc > `"$dumpPath`""
        if ((Test-Path $dumpPath) -and ((Get-Item $dumpPath).Length -gt 1024)) {
            $mb = [math]::Round((Get-Item $dumpPath).Length / 1MB, 2)
            Write-Ok "DB dump: $dumpPath ($mb MB)"
            Write-Info "restore: docker exec -i $PgContainer pg_restore -U $dbUser -d $dbName --clean < file"
        } else {
            Write-Err2 "pg_dump failed or output empty. Do NOT continue without a backup."
        }
    }
}

Write-Step "4/4  Summary"
$sizeMb = 0
if (Test-Path $dest) {
    $sum = (Get-ChildItem $dest -Recurse -File | Measure-Object Length -Sum).Sum
    if ($sum) { $sizeMb = [math]::Round($sum / 1MB, 2) }
}
Write-Ok "Backup complete: $dest ($sizeMb MB)"
Write-Host ""
Write-Host "  To undo everything later:  git reset --hard $tag" -ForegroundColor Yellow
Write-Host ""
