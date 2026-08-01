#!/usr/bin/env bash
set -euo pipefail

umask 077

if [[ -z "${DASHBOARD_PASSWORD:-}" ]]; then
  echo "DASHBOARD_PASSWORD is required" >&2
  exit 1
fi

mkdir -p \
  "${HOME}/.codex" \
  "${HOME}/.cache" \
  "${PRISM_DATA_DIR}" \
  "${PRISM_INBOX_DIR}" \
  "${HOME}/workspace"

chmod 0700 "${HOME}" "${HOME}/.codex" "${PRISM_DATA_DIR}"

echo "Prism data: ${PRISM_DATA_DIR}"
echo "Codex home: ${HOME}/.codex"
echo "Workspace: ${HOME}/workspace"

cd /app
exec python server.py
