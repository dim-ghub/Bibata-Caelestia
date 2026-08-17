#!/usr/bin/env bash
set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
TARGET_DIR="${1:-/usr/share/icons/Bibata-Caelestia}"

python3 "${SCRIPT_DIR}/builder.py" --dest "${TARGET_DIR}"
