$ErrorActionPreference = "Stop"
Set-StrictMode -Version Latest
docker compose up -d
python -m alembic upgrade head
