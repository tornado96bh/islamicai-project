$ErrorActionPreference = "Stop"
Set-StrictMode -Version Latest
python -m pip install -U pip setuptools wheel
python -m pip install -e .
