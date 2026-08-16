# Build (if needed) and run the FinAlly container. Idempotent.
[CmdletBinding()]
param(
    [switch]$Build,
    [switch]$NoBrowser,
    [int]$Port = 8000
)

$ErrorActionPreference = "Stop"

$Image = "finally"
$Container = "finally"
$Root = Split-Path -Parent $PSScriptRoot

if (-not (Get-Command docker -ErrorAction SilentlyContinue)) {
    Write-Error "docker is not installed or not on PATH."
}

$DbDir = Join-Path $Root "db"
if (-not (Test-Path $DbDir)) { New-Item -ItemType Directory -Path $DbDir | Out-Null }

$EnvFile = Join-Path $Root ".env"
if (-not (Test-Path $EnvFile)) {
    Write-Host "No .env found - creating one from .env.example."
    Copy-Item (Join-Path $Root ".env.example") $EnvFile
    Write-Host "Edit $EnvFile and set OPENROUTER_API_KEY to enable AI chat."
}

$existingImage = docker images -q $Image
if ($Build -or [string]::IsNullOrWhiteSpace($existingImage)) {
    Write-Host "Building image '$Image'..."
    docker build -t $Image $Root
}

$running = docker ps -q -f "name=^$Container$"
if (-not [string]::IsNullOrWhiteSpace($running)) {
    Write-Host "Container '$Container' is already running."
}
else {
    docker rm -f $Container 2>$null | Out-Null
    docker run -d `
        --name $Container `
        -p "$($Port):8000" `
        --env-file $EnvFile `
        -v "$($DbDir):/app/db" `
        $Image | Out-Null
    Write-Host "Started container '$Container'."
}

$Url = "http://localhost:$Port"
Write-Host "FinAlly is available at $Url"

if (-not $NoBrowser) { Start-Process $Url }
