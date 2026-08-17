#!/usr/bin/env bash
set -e

TARGET_USER="${SUDO_USER:-$USER}"
TARGET_HOME="$(getent passwd "${TARGET_USER}" | cut -d: -f6)"
TARGET_HOME="${TARGET_HOME:-$HOME}"

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
TEMPLATES_SRC="${SCRIPT_DIR}/templates"
TEMPLATES_DEST="${TARGET_HOME}/.config/caelestia/templates/bibata"
BUILDER_SRC="${SCRIPT_DIR}/builder.py"
SYS_BIN="/usr/local/bin/bibata-caelestia-builder"
USER_BIN="${TARGET_HOME}/.local/bin/bibata-caelestia-builder"
SUDOERS_FILE="/etc/sudoers.d/caelestia-bibata"
CLI_JSON="${TARGET_HOME}/.config/caelestia/cli.json"
HYPR_VARS_LUA="${TARGET_HOME}/.config/caelestia/hypr-vars.lua"
HYPR_VARS_CONF="${TARGET_HOME}/.config/caelestia/hypr-vars.conf"

# Detect existing configured size or default to 14
DEFAULT_SIZE="14"
if [ -f "${HYPR_VARS_LUA}" ]; then
    DETECTED_SIZE=$(grep -oP 'cursorSize\s*=\s*\K[0-9]+' "${HYPR_VARS_LUA}" | head -1 || true)
    if [ -n "${DETECTED_SIZE}" ]; then
        DEFAULT_SIZE="${DETECTED_SIZE}"
    fi
fi

# Prompt user for cursor size
if [ -t 0 ] || [ -e /dev/tty ]; then
    read -r -p "Enter desired cursor size [default: ${DEFAULT_SIZE}]: " INPUT_SIZE < /dev/tty || INPUT_SIZE=""
    CURSOR_SIZE="${INPUT_SIZE:-$DEFAULT_SIZE}"
else
    CURSOR_SIZE="${DEFAULT_SIZE}"
fi
echo "==> Using cursor size: ${CURSOR_SIZE}px"

echo "==> [1/6] Configuring cursor in ${HYPR_VARS_LUA}..."
python3 - <<EOF
import re
from pathlib import Path

lua_path = Path("${HYPR_VARS_LUA}")
if lua_path.exists():
    content = lua_path.read_text(encoding="utf-8")
    if "cursorTheme" in content:
        content = re.sub(r'cursorTheme\s*=\s*"[^"]*"', 'cursorTheme                = "Bibata-Caelestia"', content)
    else:
        content = content.replace("return {", 'return {\n    cursorTheme                = "Bibata-Caelestia",')
    if "cursorSize" in content:
        content = re.sub(r'cursorSize\s*=\s*[0-9]+', f'cursorSize                 = ${CURSOR_SIZE}', content)
    else:
        content = content.replace("return {", f'return {{\n    cursorSize                 = ${CURSOR_SIZE},')
    lua_path.write_text(content, encoding="utf-8")
else:
    lua_path.parent.mkdir(parents=True, exist_ok=True)
    lua_path.write_text(f'return {{\n    cursorTheme                = "Bibata-Caelestia",\n    cursorSize                 = ${CURSOR_SIZE},\n}}\n', encoding="utf-8")

conf_path = Path("${HYPR_VARS_CONF}")
if conf_path.exists():
    c_content = conf_path.read_text(encoding="utf-8")
    c_content = re.sub(r'(\$cursorTheme\s*=\s*)[^\n]+', r'\1Bibata-Caelestia', c_content)
    c_content = re.sub(r'(\$cursorSize\s*=\s*)[^\n]+', rf'\g<1>${CURSOR_SIZE}', c_content)
    conf_path.write_text(c_content, encoding="utf-8")
EOF
chown "${TARGET_USER}:${TARGET_USER}" "${HYPR_VARS_LUA}" "${HYPR_VARS_CONF}" 2>/dev/null || true

echo "==> [2/6] Installing Bibata Caelestia cursor templates..."
mkdir -p "${TEMPLATES_DEST}"
cp -f "${TEMPLATES_SRC}"/*.svg "${TEMPLATES_DEST}/"
chown -R "${TARGET_USER}:${TARGET_USER}" "${TEMPLATES_DEST}" 2>/dev/null || true
echo "    Installed 164 templates to ${TEMPLATES_DEST}"

echo "==> [3/6] Installing builder executable to ${SYS_BIN}..."
mkdir -p "${TARGET_HOME}/.local/bin"
install -m 755 "${BUILDER_SRC}" "${USER_BIN}"
chown "${TARGET_USER}:${TARGET_USER}" "${USER_BIN}" 2>/dev/null || true
if [ "$EUID" -eq 0 ]; then
    install -m 755 "${BUILDER_SRC}" "${SYS_BIN}"
else
    sudo install -m 755 "${BUILDER_SRC}" "${SYS_BIN}"
fi
echo "    Installed ${SYS_BIN}"

echo "==> [4/6] Configuring sudoers rule in ${SUDOERS_FILE}..."
SUDOERS_LINE="${TARGET_USER} ALL=(ALL) NOPASSWD: ${SYS_BIN}"
if [ "$EUID" -eq 0 ]; then
    echo "${SUDOERS_LINE}" > "${SUDOERS_FILE}"
    chmod 440 "${SUDOERS_FILE}"
else
    echo "${SUDOERS_LINE}" | sudo tee "${SUDOERS_FILE}" >/dev/null
    sudo chmod 440 "${SUDOERS_FILE}"
fi
echo "    Configured passwordless sudo for ${TARGET_USER} -> ${SYS_BIN}"

echo "==> [5/6] Updating Caelestia CLI post hooks in ${CLI_JSON}..."
python3 - <<EOF
import json
from pathlib import Path

cli_json_path = Path("${CLI_JSON}")
cmd = "sudo ${SYS_BIN}"

if cli_json_path.exists():
    try:
        data = json.loads(cli_json_path.read_text())
    except Exception:
        data = {}
else:
    data = {}

# Update theme.postHook
theme_cfg = data.setdefault("theme", {})
theme_hook = theme_cfg.get("postHook", "")
if cmd not in theme_hook:
    theme_cfg["postHook"] = (theme_hook + f" && {cmd}").strip(" &")

# Update wallpaper.postHook
wp_cfg = data.setdefault("wallpaper", {})
wp_hook = wp_cfg.get("postHook", "")
if cmd not in wp_hook:
    wp_cfg["postHook"] = (wp_hook + f" && {cmd}").strip(" &")

cli_json_path.parent.mkdir(parents=True, exist_ok=True)
cli_json_path.write_text(json.dumps(data, indent=4))
print("    Updated cli.json post hooks successfully.")
EOF

echo "==> [6/6] Building cursors and applying size ${CURSOR_SIZE}px..."
if [ "$EUID" -eq 0 ]; then
    "${SYS_BIN}" --size "${CURSOR_SIZE}" --dest "/usr/share/icons/Bibata-Caelestia"
else
    sudo "${SYS_BIN}" --size "${CURSOR_SIZE}" --dest "/usr/share/icons/Bibata-Caelestia"
fi

echo "==> Installation complete! Bibata-Caelestia is ready."
