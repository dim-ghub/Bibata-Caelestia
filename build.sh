#!/usr/bin/env bash
set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

case "${1:-build}" in
    preview)
        shift
        python3 "${SCRIPT_DIR}/builder.py" preview "$@"
        ;;
    build|*)
        TARGET_DIR="${1:-/usr/share/icons/Bibata-Caelestia}"
        python3 "${SCRIPT_DIR}/builder.py" build --dest "${TARGET_DIR}"
        ;;
esac
