#!/usr/bin/env bash
# Clona los repos OCA que nuestros módulos requieren.
# Idempotente: si ya existe, hace pull --ff-only.
set -euo pipefail

cd "$(dirname "$0")/.."
mkdir -p oca-deps
cd oca-deps

BRANCH=18.0
REPOS=(
  "OCA/server-tools"          # base_technical_features, server_action_navigate
  "OCA/server-ux"             # date_range (PLE)
  "OCA/account-financial-reporting"  # reportes de Balance / P&G
  "OCA/reporting-engine"      # report_xlsx (export PLE/SIRE preview)
  "OCA/queue"                 # queue_job para envíos asíncronos a SUNAT
  "OCA/web"                   # web_widget_* varios
)

for repo in "${REPOS[@]}"; do
  name="${repo##*/}"
  if [[ -d "$name/.git" ]]; then
    echo "→ $name: pull"
    (cd "$name" && git fetch --depth 1 origin "$BRANCH" && git reset --hard "origin/$BRANCH")
  else
    echo "→ $name: clone"
    git clone --depth 1 --branch "$BRANCH" "https://github.com/$repo.git" "$name"
  fi
done

echo
echo "✓ OCA deps en $(pwd)"
ls -1
