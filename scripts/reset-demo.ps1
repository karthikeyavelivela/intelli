# One-command demo reset (Windows). DESTRUCTIVE: wipes ALL data, then re-seeds.
$ErrorActionPreference = "Stop"
Set-Location (Join-Path $PSScriptRoot "..")
$running = $false
if (Get-Command docker -ErrorAction SilentlyContinue) {
  $running = [bool]((docker compose ps --status running backend 2>$null) -match "backend")
}
if ($running) {
  docker compose exec -T backend python -m app.seed --reset
} else {
  Push-Location backend
  if (Test-Path ".venv\Scripts\python.exe") { .\.venv\Scripts\python.exe -m app.seed --reset } else { python -m app.seed --reset }
  Pop-Location
}
