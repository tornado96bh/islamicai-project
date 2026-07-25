<#
.SYNOPSIS
  Rotate credentials and untrack .env (the repo is public; .env was committed).
#>
[CmdletBinding()]
param([switch]$DryRun, [switch]$KeepPasswords)
. "$PSScriptRoot\_common.ps1"
Assert-RepoRoot

Write-Step "1/5  Read current settings"
$cur = @{}
if (Test-Path .env) {
    foreach ($line in (Read-Utf8 ".env") -split "`n") {
        $l = $line.Trim([char]0xFEFF).Trim()
        if ($l -and -not $l.StartsWith("#") -and $l.Contains("=")) {
            $k, $v = $l -split "=", 2
            $cur[$k.Trim()] = $v.Trim()
        }
    }
    Write-Ok ("read .env - " + $cur.Count + " keys")
} else { Write-Warn2 ".env not found, will create it" }

function Get-Val { param($k, $d) if ($cur.ContainsKey($k) -and $cur[$k]) { return $cur[$k] } else { return $d } }

Write-Step "2/5  Generate new passwords"
if ($KeepPasswords) {
    $pgPass    = Get-Val "POSTGRES_PASSWORD"   "change_me"
    $minioPass = Get-Val "MINIO_ROOT_PASSWORD" "change_me_too"
    $neoPass   = Get-Val "NEO4J_PASSWORD"      "change_me"
    Write-Warn2 "-KeepPasswords set: passwords NOT rotated."
} else {
    $pgPass = New-StrongPassword 32
    $minioPass = New-StrongPassword 32
    $neoPass = New-StrongPassword 32
    Write-Ok "generated 3 new 32-char cryptographic passwords"
}

Write-Step "3/5  Write .env and .env.example"
$envBody = @"
# IslamicAI local settings. NEVER commit this file.
# Generated: $(Get-Date -Format "yyyy-MM-dd HH:mm")

POSTGRES_HOST=$(Get-Val "POSTGRES_HOST" "localhost")
POSTGRES_PORT=$(Get-Val "POSTGRES_PORT" "5432")
POSTGRES_DB=$(Get-Val "POSTGRES_DB" "islamicai")
POSTGRES_USER=$(Get-Val "POSTGRES_USER" "islamicai")
POSTGRES_PASSWORD=$pgPass

REDIS_HOST=$(Get-Val "REDIS_HOST" "localhost")
REDIS_PORT=$(Get-Val "REDIS_PORT" "6379")

MINIO_ROOT_USER=$(Get-Val "MINIO_ROOT_USER" "islamicai")
MINIO_ROOT_PASSWORD=$minioPass
MINIO_PORT=$(Get-Val "MINIO_PORT" "9000")
MINIO_CONSOLE_PORT=$(Get-Val "MINIO_CONSOLE_PORT" "9001")

QDRANT_PORT=$(Get-Val "QDRANT_PORT" "6333")
QDRANT_URL=$(Get-Val "QDRANT_URL" "http://localhost:6333")
QDRANT_COLLECTION=$(Get-Val "QDRANT_COLLECTION" "islamicai_pages")
QDRANT_TIMEOUT=$(Get-Val "QDRANT_TIMEOUT" "15")
QDRANT_BATCH_SIZE=$(Get-Val "QDRANT_BATCH_SIZE" "50")
QDRANT_RETRIES=$(Get-Val "QDRANT_RETRIES" "4")

NEO4J_USER=neo4j
NEO4J_PASSWORD=$neoPass
NEO4J_HTTP_PORT=$(Get-Val "NEO4J_HTTP_PORT" "7474")
NEO4J_BOLT_PORT=$(Get-Val "NEO4J_BOLT_PORT" "7687")

BACKEND_PORT=$(Get-Val "BACKEND_PORT" "8000")
"@

$exampleBody = $envBody `
    -replace "POSTGRES_PASSWORD=.*",   "POSTGRES_PASSWORD=<set-a-strong-password>" `
    -replace "MINIO_ROOT_PASSWORD=.*", "MINIO_ROOT_PASSWORD=<set-a-strong-password>" `
    -replace "NEO4J_PASSWORD=.*",      "NEO4J_PASSWORD=<set-a-strong-password>"

if ($DryRun) {
    Write-Dry "would write .env (new passwords) and .env.example (placeholders)"
} else {
    if (Test-Path .env) {
        $safe = "..\islamicai-env-backup-$(Get-Stamp).txt"
        Copy-Item .env $safe -Force
        Write-Ok "old .env copied outside the repo: $safe"
    }
    Write-Utf8NoBom -Path ".env" -Content $envBody
    Write-Utf8NoBom -Path ".env.example" -Content $exampleBody
    Write-Ok "wrote .env and .env.example"
}

Write-Step "4/5  Untrack .env from git"
Remove-FromGitIndex -PathSpec ".env"     -DryRun:$DryRun | Out-Null
Remove-FromGitIndex -PathSpec ".env.bak" -DryRun:$DryRun | Out-Null
if (-not $DryRun -and (Test-Path ".env.bak")) {
    Remove-Item ".env.bak" -Force
    Write-Ok "deleted .env.bak from disk (a copy is outside the repo)"
}

Write-Step "5/5  Fix hardcoded neo4j password in docker-compose"
if (Test-Path "docker-compose.yml") {
    $dc = Read-Utf8 "docker-compose.yml"
    if ($dc -match 'NEO4J_AUTH:\s*neo4j/change_me') {
        if ($DryRun) { Write-Dry "would replace NEO4J_AUTH with env variable" }
        else {
            $dc = $dc -replace 'NEO4J_AUTH:\s*neo4j/change_me', 'NEO4J_AUTH: neo4j/${NEO4J_PASSWORD}'
            Write-Utf8NoBom -Path "docker-compose.yml" -Content $dc
            Write-Ok "NEO4J_AUTH now reads from .env"
        }
    } else { Write-Info "NEO4J_AUTH already customised - untouched" }
}

Write-Host ""
Write-Host "  MANUAL STEPS:" -ForegroundColor Yellow
Write-Host "   1) An existing database keeps its OLD password until you run" -ForegroundColor Yellow
Write-Host "      ALTER USER, or recreate the volume: docker compose down -v" -ForegroundColor Yellow
Write-Host "   2) Old secrets remain in git history. Rotation above is the real fix." -ForegroundColor Yellow
Write-Host ""
