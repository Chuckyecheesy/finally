# Stop and remove the FinAlly container. Data in .\db is left untouched.
[CmdletBinding()]
param()

$ErrorActionPreference = "Stop"

$Container = "finally"

if (-not (Get-Command docker -ErrorAction SilentlyContinue)) {
    Write-Error "docker is not installed or not on PATH."
}

$existing = docker ps -aq -f "name=^$Container$"
if (-not [string]::IsNullOrWhiteSpace($existing)) {
    docker rm -f $Container | Out-Null
    Write-Host "Stopped and removed container '$Container'. Database in .\db is preserved."
}
else {
    Write-Host "Container '$Container' is not running."
}
