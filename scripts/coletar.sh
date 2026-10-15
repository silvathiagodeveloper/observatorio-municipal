#!/usr/bin/env bash
# Roda a coleta em segundo plano, com log. Uso: scripts/coletar.sh config/tijucas.yaml
set -euo pipefail
cd "$(dirname "$0")/.."
cfg="${1:-config/tijucas.yaml}"
mkdir -p dados
PYTHONPATH=src nohup python3 -u -m observatorio.coleta "$cfg" > dados/coleta.log 2>&1 &
echo "coleta iniciada (pid $!) — acompanhe em dados/coleta.log"
