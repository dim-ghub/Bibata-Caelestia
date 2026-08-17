#!/usr/bin/env python3
"""
Bibata-Caelestia Ultra-Fast In-Memory XCursor Builder
Generates X11 cursor binaries directly from SVG templates using librsvg + cairo.
"""

import argparse
import concurrent.futures
import json
import os
import re
import shutil
import struct
import subprocess
import sys
import time
from pathlib import Path

import warnings
warnings.filterwarnings("ignore")

import gi
gi.require_version("Rsvg", "2.0")
from gi.repository import Rsvg
import cairo

# Cursor configurations: hotspots, delays, symlinks
# Hotspots are normalized to 256x256 viewBox
FALLBACK_SIZES = [14, 16, 20, 22, 24, 28, 32, 40, 48, 56, 64, 72, 80, 88, 96]
DEFAULT_XHOT = 128
DEFAULT_YHOT = 128
DEFAULT_DELAY = 40

CURSOR_CONFIG = {
    "bd_double_arrow": {
        "png": "bd_double_arrow.png",
        "symlinks": ["c7088f0f3e6c8088236ef8e1e3e70000", "nwse-resize", "size_fdiag"],
    },
    "bottom_left_corner": {
        "png": "bottom_left_corner.png",
        "x_hotspot": 26,
        "y_hotspot": 232,
        "symlinks": ["sw-resize"],
    },
    "bottom_right_corner": {
        "png": "bottom_right_corner.png",
        "x_hotspot": 229,
        "y_hotspot": 232,
        "symlinks": ["se-resize"],
    },
    "bottom_side": {
        "png": "bottom_side.png",
        "x_hotspot": 129,
        "y_hotspot": 234,
        "symlinks": ["s-resize"],
    },
    "bottom_tee": {
        "png": "bottom_tee.png",
        "x_hotspot": 128,
        "y_hotspot": 230,
    },
    "center_ptr": {
        "png": "center_ptr.png",
        "x_hotspot": 127,
        "y_hotspot": 17,
    },
    "circle": {
        "png": "circle.png",
        "x_hotspot": 55,
        "y_hotspot": 17,
        "symlinks": ["forbidden"],
    },
    "context-menu": {
        "png": "context-menu.png",
        "x_hotspot": 57,
        "y_hotspot": 17,
    },
    "copy": {
        "png": "copy.png",
        "x_hotspot": 55,
        "y_hotspot": 17,
        "symlinks": [
            "1081e37283d90000800003c07f3ef6bf",
            "6407b0e94181790501fd1e167b474872",
            "b66166c04f8c3109214a4fbd64a50fc8",
        ],
    },
    "cross": {
        "png": "cross.png",
        "symlinks": ["cross_reverse", "diamond_cross"],
    },
    "crossed_circle": {
        "png": "crossed_circle.png",
        "symlinks": ["03b6e0fcb3499374a867c041f52298f0", "not-allowed"],
    },
    "crosshair": {
        "png": "crosshair.png",
    },
    "dnd_no_drop": {
        "png": "dnd_no_drop.png",
        "x_hotspot": 100,
        "y_hotspot": 65,
        "symlinks": ["no-drop"],
    },
    "dnd-ask": {
        "png": "dnd-ask.png",
        "x_hotspot": 100,
        "y_hotspot": 65,
    },
    "dnd-copy": {
        "png": "dnd-copy.png",
        "x_hotspot": 100,
        "y_hotspot": 65,
    },
    "dnd-link": {
        "png": "dnd-link.png",
        "x_hotspot": 100,
        "y_hotspot": 65,
        "symlinks": ["alias"],
    },
    "dotbox": {
        "png": "dotbox.png",
        "symlinks": ["dot_box_mask", "draped_box", "icon", "target"],
    },
    "fd_double_arrow": {
        "png": "fd_double_arrow.png",
        "symlinks": ["fcf1c3c7cd4491d801f1e1c78f100000", "nesw-resize", "size_bdiag"],
    },
    "grabbing": {
        "png": "grabbing.png",
        "x_hotspot": 128,
        "y_hotspot": 66,
        "symlinks": [
            "closedhand",
            "dnd-move",
            "dnd-none",
            "fcf21c00b30f7e3f83fe0dfd12e71cff",
        ],
    },
    "hand1": {
        "png": "hand1.png",
        "x_hotspot": 144,
        "y_hotspot": 79,
        "symlinks": ["grab", "openhand"],
    },
    "hand2": {
        "png": "hand2.png",
        "x_hotspot": 114,
        "y_hotspot": 18,
        "symlinks": [
            "9d800788f1b08800ae810202380a0822",
            "e29285e634086352946a0e7090d73106",
            "pointer",
            "pointing_hand",
        ],
    },
    "left_ptr": {
        "png": "left_ptr.png",
        "x_hotspot": 55,
        "y_hotspot": 17,
        "symlinks": ["arrow", "default", "top_left_arrow"],
    },
    "left_ptr_watch": {
        "png": "left_ptr_watch-*.png",
        "x_hotspot": 55,
        "y_hotspot": 17,
        "symlinks": [
            "00000000000000020006000e7e9ffc3f",
            "08e8e1c95fe2fc01f976f1e063a24ccd",
            "3ecb610c1bf2410f44200f48c40d3599",
            "progress",
        ],
    },
    "left_side": {
        "png": "left_side.png",
        "x_hotspot": 21,
        "y_hotspot": 128,
        "symlinks": ["w-resize"],
    },
    "left_tee": {
        "png": "left_tee.png",
        "x_hotspot": 230,
        "y_hotspot": 128,
    },
    "link": {
        "png": "link.png",
        "x_hotspot": 55,
        "y_hotspot": 17,
        "symlinks": [
            "3085a0e285430894940527032f8b26df",
            "640fb0e74195791501fd1ed57b41487f",
            "a2a266d0498c3104214a47bd64ab0fc8",
        ],
    },
    "ll_angle": {
        "png": "ll_angle.png",
        "x_hotspot": 30,
        "y_hotspot": 223,
    },
    "lr_angle": {
        "png": "lr_angle.png",
        "x_hotspot": 224,
        "y_hotspot": 230,
    },
    "move": {
        "png": "move.png",
        "symlinks": [
            "4498f0e0c1937ffe01fd06f973665830",
            "9081237383d90e509aa00f00170e968f",
            "all-scroll",
            "fleur",
            "size_all",
        ],
    },
    "pencil": {
        "png": "pencil.png",
        "x_hotspot": 46,
        "y_hotspot": 211,
        "symlinks": ["draft"],
    },
    "plus": {
        "png": "plus.png",
        "symlinks": ["cell"],
    },
    "pointer-move": {
        "png": "pointer-move.png",
        "x_hotspot": 55,
        "y_hotspot": 17,
    },
    "question_arrow": {
        "png": "question_arrow.png",
        "x_hotspot": 42,
        "y_hotspot": 86,
        "symlinks": [
            "5c6cd98b3f3ebcb1f9c7f1c204630408",
            "d9ce0ab605698f320427677b458ad60b",
            "help",
            "left_ptr_help",
            "whats_this",
        ],
    },
    "right_ptr": {
        "png": "right_ptr.png",
        "x_hotspot": 204,
        "y_hotspot": 17,
        "symlinks": ["draft_large", "draft_small"],
    },
    "right_side": {
        "png": "right_side.png",
        "x_hotspot": 233,
        "y_hotspot": 128,
        "symlinks": ["e-resize"],
    },
    "right_tee": {
        "png": "right_tee.png",
        "x_hotspot": 29,
        "y_hotspot": 128,
    },
    "sb_down_arrow": {
        "png": "sb_down_arrow.png",
        "x_hotspot": 128,
        "y_hotspot": 222,
        "symlinks": ["down-arrow"],
    },
    "sb_h_double_arrow": {
        "png": "sb_h_double_arrow.png",
        "symlinks": [
            "028006030e0e7ebffc7f7070c0600140",
            "14fef782d02440884392942c1120523",
            "col-resize",
            "ew-resize",
            "h_double_arrow",
            "size-hor",
            "size_hor",
            "split_h",
        ],
    },
    "sb_left_arrow": {
        "png": "sb_left_arrow.png",
        "x_hotspot": 33,
        "y_hotspot": 128,
        "symlinks": ["left-arrow"],
    },
    "sb_right_arrow": {
        "png": "sb_right_arrow.png",
        "x_hotspot": 223,
        "y_hotspot": 128,
        "symlinks": ["right-arrow"],
    },
    "sb_up_arrow": {
        "png": "sb_up_arrow.png",
        "x_hotspot": 128,
        "y_hotspot": 33,
        "symlinks": ["up-arrow"],
    },
    "sb_v_double_arrow": {
        "png": "sb_v_double_arrow.png",
        "symlinks": [
            "00008160000006810000408080010102",
            "2870a09082c103050810ffdffffe0204",
            "double_arrow",
            "ns-resize",
            "row-resize",
            "size-ver",
            "size_ver",
            "split_v",
            "v_double_arrow",
        ],
    },
    "tcross": {
        "png": "tcross.png",
        "symlinks": ["color-picker"],
    },
    "top_left_corner": {
        "png": "top_left_corner.png",
        "x_hotspot": 29,
        "y_hotspot": 24,
        "symlinks": ["nw-resize"],
    },
    "top_right_corner": {
        "png": "top_right_corner.png",
        "x_hotspot": 229,
        "y_hotspot": 24,
        "symlinks": ["ne-resize"],
    },
    "top_side": {
        "png": "top_side.png",
        "x_hotspot": 128,
        "y_hotspot": 23,
        "symlinks": ["n-resize"],
    },
    "top_tee": {
        "png": "top_tee.png",
        "x_hotspot": 128,
        "y_hotspot": 27,
    },
    "ul_angle": {
        "png": "ul_angle.png",
        "x_hotspot": 33,
        "y_hotspot": 33,
    },
    "ur_angle": {
        "png": "ur_angle.png",
        "x_hotspot": 225,
        "y_hotspot": 33,
    },
    "vertical-text": {
        "png": "vertical-text.png",
    },
    "wait": {
        "png": "wait-*.png",
        "symlinks": ["watch"],
    },
    "wayland-cursor": {
        "png": "wayland-cursor.png",
    },
    "X_cursor": {
        "png": "X_cursor.png",
        "symlinks": ["pirate", "x-cursor"],
    },
    "xterm": {
        "png": "xterm.png",
        "symlinks": ["ibeam", "text"],
    },
    "zoom-in": {
        "png": "zoom-in.png",
        "x_hotspot": 116,
        "y_hotspot": 116,
    },
    "zoom-out": {
        "png": "zoom-out.png",
        "x_hotspot": 116,
        "y_hotspot": 116,
    },
}


class DynamicColour:
    def __init__(self, hex_val: str):
        hex_val = hex_val.ljust(8, "f").removeprefix("#")
        self._hex_vals = tuple(hex_val[i : i + 2] for i in range(0, 7, 2))
        self._rgb_vals = tuple(int(h, 16) for h in self._hex_vals)
        self._hsl_vals = self._to_hsl(self._rgb_vals)

    @property
    def hex(self) -> str:
        return "".join(self._hex_vals[:-1])

    @property
    def rgb(self) -> str:
        return f"rgb({','.join(map(str, self._rgb_vals[:-1]))})"

    @staticmethod
    def _to_hsl(rgb: tuple[int, ...]) -> tuple[int, int, int]:
        r, g, b = (v / 255.0 for v in rgb[:3])
        cmax, cmin = max(r, g, b), min(r, g, b)
        delta = cmax - cmin
        lightness = (cmax + cmin) / 2.0
        saturation = 0.0 if delta == 0 else delta / (1.0 - abs(2.0 * lightness - 1.0))
        if delta == 0:
            hue = 0.0
        elif cmax == r:
            hue = 60.0 * (((g - b) / delta) % 6.0)
        elif cmax == g:
            hue = 60.0 * (((b - r) / delta) + 2.0)
        else:
            hue = 60.0 * (((r - g) / delta) + 4.0)
        return round(hue), round(saturation * 100.0), round(lightness * 100.0)


def render_template(template_str: str, colours: dict[str, str], mode: str = "dark") -> str:
    dyn = {k: DynamicColour(v) for k, v in colours.items()}

    def repl(m: re.Match) -> str:
        parts = m.group(1).strip().split(".")
        if len(parts) == 2:
            col, prop = parts
            if col in dyn and hasattr(dyn[col], prop):
                return str(getattr(dyn[col], prop))
        return m.group(0)

    res = re.sub(r"\{\{((?:(?!\{\{|\}\}).)*)\}\}", repl, template_str)
    res = re.sub(r"\{\{\s*mode\s*\}\}", mode, res)
    return res


def get_possible_user_homes() -> list[Path]:
    homes = []
    if sudo_user := os.environ.get("SUDO_USER"):
        try:
            import pwd
            homes.append(Path(pwd.getpwnam(sudo_user).pw_dir))
        except Exception:
            pass
    if user := os.environ.get("USER"):
        try:
            import pwd
            homes.append(Path(pwd.getpwnam(user).pw_dir))
        except Exception:
            pass
    homes.append(Path.home())
    home_parent = Path("/home")
    if home_parent.is_dir():
        for d in home_parent.iterdir():
            if d.is_dir() and d not in homes:
                homes.append(d)
    return homes


def load_caelestia_colours() -> tuple[dict[str, str], str]:
    if env_colours := os.getenv("SCHEME_COLOURS"):
        try:
            colours = json.loads(env_colours)
            mode = os.getenv("SCHEME_MODE", "dark")
            return colours, mode
        except Exception:
            pass

    for home in get_possible_user_homes():
        state_scheme = home / ".local/state/caelestia/scheme.json"
        if state_scheme.is_file():
            try:
                data = json.loads(state_scheme.read_text())
                return data["colours"], data.get("mode", "dark")
            except Exception:
                pass

    # Default fallback
    return {
        "surface": "0a0f0f",
        "primary": "9bd0cc",
        "secondary": "b0ccc9",
        "tertiary": "d5efff",
        "outline": "6d7876",
        "onSurface": "dce8e6",
        "surfaceContainerHigh": "192120",
        "blue": "57cdda",
        "green": "8df1df",
        "yellow": "d3fae8",
        "red": "8ab5ff",
    }, "dark"


def pack_xcursor(images: list) -> bytes:
    # images: list of (nominal_size, width, height, xhot, yhot, delay, bgra_bytes)
    ntoc = len(images)
    header_size = 16
    toc_size = ntoc * 12
    offset = header_size + toc_size
    tocs = []
    chunks = []
    for size, w, h, xhot, yhot, delay, pixels in images:
        chunk_header = struct.pack("<IIII", 16, 0xfffd0002, size, 1)
        img_info = struct.pack("<IIIII", w, h, xhot, yhot, delay)
        chunk = chunk_header + img_info + pixels
        tocs.append(struct.pack("<III", 0xfffd0002, size, offset))
        offset += len(chunk)
        chunks.append(chunk)
    header = struct.pack("<4sIII", b"Xcur", 16, 0x10000, ntoc)
    return header + b"".join(tocs) + b"".join(chunks)


def find_svg_sources() -> dict[str, str]:
    # Returns map of filename -> svg text
    svg_map: dict[str, str] = {}
    search_dirs: list[Path] = []

    # Check template directories FIRST so templates are rendered fresh with current scheme
    for home in get_possible_user_homes():
        search_dirs.append(home / ".config/caelestia/templates/bibata")

    search_dirs.append(Path(__file__).parent / "templates")

    # Fallback to pre-rendered theme state if templates not found
    for home in get_possible_user_homes():
        search_dirs.extend([
            home / ".local/state/caelestia/theme/bibata",
            home / ".local/state/caelestia/theme",
        ])

    colours, mode = load_caelestia_colours()

    for directory in search_dirs:
        if directory.is_dir():
            for svg_file in directory.glob("*.svg"):
                if svg_file.name not in svg_map:
                    try:
                        content = svg_file.read_text(encoding="utf-8")
                        if "{{" in content:
                            content = render_template(content, colours, mode)
                        svg_map[svg_file.name] = content
                    except Exception:
                        pass

    return svg_map


def build_single_cursor(name: str, config: dict, svg_map: dict[str, str], sizes: list[int]) -> tuple[str, bytes]:
    png_pattern = config["png"]
    xhot = config.get("x_hotspot", DEFAULT_XHOT)
    yhot = config.get("y_hotspot", DEFAULT_YHOT)
    delay = config.get("x11_delay", DEFAULT_DELAY)

    images = []

    if "*" in png_pattern:
        prefix = png_pattern.replace("-*.png", "")
        matching = sorted([k for k in svg_map if k.startswith(prefix + "-") and k.endswith(".svg")])
        for frame in matching:
            svg_data = svg_map[frame].encode("utf-8")
            handle = Rsvg.Handle.new_from_data(svg_data)
            for size in sizes:
                surf = cairo.ImageSurface(cairo.FORMAT_ARGB32, size, size)
                cr = cairo.Context(surf)
                cr.scale(size / 256.0, size / 256.0)
                handle.render_cairo(cr)
                surf.flush()
                sxhot = int(round(xhot * size / 256.0))
                syhot = int(round(yhot * size / 256.0))
                images.append((size, size, size, sxhot, syhot, delay, bytes(surf.get_data())))
    else:
        svg_name = png_pattern.replace(".png", ".svg")
        if svg_name in svg_map:
            svg_data = svg_map[svg_name].encode("utf-8")
            handle = Rsvg.Handle.new_from_data(svg_data)
            for size in sizes:
                surf = cairo.ImageSurface(cairo.FORMAT_ARGB32, size, size)
                cr = cairo.Context(surf)
                cr.scale(size / 256.0, size / 256.0)
                handle.render_cairo(cr)
                surf.flush()
                sxhot = int(round(xhot * size / 256.0))
                syhot = int(round(yhot * size / 256.0))
                images.append((size, size, size, sxhot, syhot, delay, bytes(surf.get_data())))

    if images:
        return name, pack_xcursor(images)
    return name, b""


def is_dir_writable(path: Path) -> bool:
    try:
        path.mkdir(parents=True, exist_ok=True)
        test_file = path / ".write_test"
        test_file.write_text("test", encoding="utf-8")
        test_file.unlink()
        return True
    except Exception:
        return False


def reload_system_cursors(theme_name: str = "Bibata-Caelestia", size: int = 24) -> None:
    sudo_user = os.environ.get("SUDO_USER")
    user = sudo_user or os.environ.get("USER") or "dim"

    try:
        import pwd
        pw = pwd.getpwnam(user)
        home = Path(pw.pw_dir)
        uid = pw.pw_uid
    except Exception:
        home = Path.home()
        uid = os.getuid()

    # Build clean environment with user's runtime paths
    user_env = os.environ.copy()
    user_env["HOME"] = str(home)
    user_env["USER"] = user
    user_env["LOGNAME"] = user
    user_env["XDG_RUNTIME_DIR"] = f"/run/user/{uid}"

    # Connect to user's DBus session bus
    dbus_bus = Path(f"/run/user/{uid}/bus")
    if dbus_bus.exists():
        user_env["DBUS_SESSION_BUS_ADDRESS"] = f"unix:path={dbus_bus}"

    # Detect active X11 display if not set
    if "DISPLAY" not in user_env:
        import glob
        x_sockets = sorted(glob.glob("/tmp/.X11-unix/X*"))
        if x_sockets:
            disp_num = Path(x_sockets[0]).name.removeprefix("X")
            user_env["DISPLAY"] = f":{disp_num}"
        else:
            user_env["DISPLAY"] = ":0"

    # Detect active Wayland display if not set
    if "WAYLAND_DISPLAY" not in user_env:
        import glob
        w_sockets = sorted(glob.glob(f"/run/user/{uid}/wayland-*"))
        if w_sockets:
            user_env["WAYLAND_DISPLAY"] = Path(w_sockets[0]).name
        else:
            user_env["WAYLAND_DISPLAY"] = "wayland-1"

    def run_as_user(cmd_list: list[str], extra_env: dict | None = None) -> None:
        cmd_env = user_env.copy()
        if extra_env:
            cmd_env.update(extra_env)
        try:
            if os.geteuid() == 0 and sudo_user:
                subprocess.run(
                    cmd_list,
                    user=user,
                    env=cmd_env,
                    stderr=subprocess.DEVNULL,
                    stdout=subprocess.DEVNULL,
                    check=False,
                )
            else:
                subprocess.run(
                    cmd_list,
                    env=cmd_env,
                    stderr=subprocess.DEVNULL,
                    stdout=subprocess.DEVNULL,
                    check=False,
                )
        except Exception:
            pass

    # 1. Update default index.theme in user icons and system icons
    default_content = f"[Icon Theme]\nName=Default\nComment=Default Cursor Theme\nInherits={theme_name}\n"
    for d in [home / ".local/share/icons/default", home / ".icons/default"]:
        try:
            d.mkdir(parents=True, exist_ok=True)
            (d / "index.theme").write_text(default_content, encoding="utf-8")
        except Exception:
            pass

    try:
        sys_def = Path("/usr/share/icons/default")
        sys_def.mkdir(parents=True, exist_ok=True)
        (sys_def / "index.theme").write_text(default_content, encoding="utf-8")
    except Exception:
        pass

    # 2. Update .Xresources and merge with xrdb
    xresources = home / ".Xresources"
    try:
        lines = []
        found_t, found_s = False, False
        if xresources.exists():
            for line in xresources.read_text().splitlines():
                if line.startswith("Xcursor.theme"):
                    lines.append(f"Xcursor.theme: {theme_name}")
                    found_t = True
                elif line.startswith("Xcursor.size"):
                    lines.append(f"Xcursor.size: {size}")
                    found_s = True
                else:
                    lines.append(line)
        if not found_t:
            lines.append(f"Xcursor.theme: {theme_name}")
        if not found_s:
            lines.append(f"Xcursor.size: {size}")
        xresources.write_text("\n".join(lines) + "\n", encoding="utf-8")
        if shutil.which("xrdb"):
            run_as_user(["xrdb", "-merge", str(xresources)])
    except Exception:
        pass

    # 3. Update GTK settings.ini for gtk-3.0 and gtk-4.0
    for gtk_dir in [home / ".config/gtk-3.0", home / ".config/gtk-4.0"]:
        try:
            gtk_dir.mkdir(parents=True, exist_ok=True)
            settings_file = gtk_dir / "settings.ini"
            lines = []
            has_settings = False
            found_t, found_s = False, False
            if settings_file.exists():
                for line in settings_file.read_text().splitlines():
                    if line.strip() == "[Settings]":
                        has_settings = True
                        lines.append(line)
                    elif has_settings and line.startswith("gtk-cursor-theme-name"):
                        lines.append(f"gtk-cursor-theme-name={theme_name}")
                        found_t = True
                    elif has_settings and line.startswith("gtk-cursor-theme-size"):
                        lines.append(f"gtk-cursor-theme-size={size}")
                        found_s = True
                    else:
                        lines.append(line)
            if not has_settings:
                lines = ["[Settings]"] + lines
            if not found_t:
                lines.append(f"gtk-cursor-theme-name={theme_name}")
            if not found_s:
                lines.append(f"gtk-cursor-theme-size={size}")
            settings_file.write_text("\n".join(lines) + "\n", encoding="utf-8")
        except Exception:
            pass

    # 4. Update dconf / gsettings
    if shutil.which("dconf"):
        run_as_user(["dconf", "write", "/org/gnome/desktop/interface/cursor-theme", f"'{theme_name}'"])
        run_as_user(["dconf", "write", "/org/gnome/desktop/interface/cursor-size", str(size)])
    if shutil.which("gsettings"):
        run_as_user(["gsettings", "set", "org.gnome.desktop.interface", "cursor-theme", theme_name])
        run_as_user(["gsettings", "set", "org.gnome.desktop.interface", "cursor-size", str(size)])

    # 5. Reload Hyprland cursors live across all active instances (with cache busting)
    if shutil.which("hyprctl"):
        import glob
        hypr_sockets = sorted(
            glob.glob(f"/run/user/{uid}/hypr/*/.socket.sock") + glob.glob("/tmp/hypr/*/.socket.sock")
        )
        seen_sigs = set()
        for sock in hypr_sockets:
            sig = Path(sock).parent.name
            if sig in seen_sigs:
                continue
            seen_sigs.add(sig)

            # Cycle cursor theme to force Hyprland / wlroots to bust internal cursor cache
            run_as_user(["hyprctl", "setcursor", "Adwaita", str(size)], {"HYPRLAND_INSTANCE_SIGNATURE": sig})
            time.sleep(0.05)
            run_as_user(["hyprctl", "setcursor", theme_name, str(size)], {"HYPRLAND_INSTANCE_SIGNATURE": sig})

        # Also run default hyprctl setcursor in current environment
        run_as_user(["hyprctl", "setcursor", "Adwaita", str(size)])
        time.sleep(0.05)
        run_as_user(["hyprctl", "setcursor", theme_name, str(size)])


def detect_cursor_size() -> int:
    for home in get_possible_user_homes():
        lua_file = home / ".config/caelestia/hypr-vars.lua"
        if lua_file.exists():
            try:
                m = re.search(r"cursorSize\s*=\s*(\d+)", lua_file.read_text())
                if m:
                    return int(m.group(1))
            except Exception:
                pass

        conf_file = home / ".config/caelestia/hypr-vars.conf"
        if conf_file.exists():
            try:
                m = re.search(r"cursorSize\s*=\s*(\d+)", conf_file.read_text())
                if m:
                    return int(m.group(1))
            except Exception:
                pass

    if env_sz := os.environ.get("XCURSOR_SIZE"):
        try:
            return int(env_sz)
        except Exception:
            pass

    return 14


def build_hyprcursor_theme(svg_map: dict[str, str], target_dir: Path) -> None:
    if not shutil.which("hyprcursor-util"):
        return

    import tempfile
    with tempfile.TemporaryDirectory() as tmpdir:
        src_dir = Path(tmpdir) / "source"
        src_dir.mkdir(parents=True, exist_ok=True)

        manifest = (
            "name = Bibata-Caelestia\n"
            "description = Bibata cursor themed dynamically with Caelestia\n"
            "version = 0.1\n"
            "cursors_directory = hyprcursors\n"
        )
        (src_dir / "manifest.hl").write_text(manifest, encoding="utf-8")

        hcursors_dir = src_dir / "hyprcursors"
        hcursors_dir.mkdir(parents=True, exist_ok=True)

        for name, cfg in CURSOR_CONFIG.items():
            cur_dir = hcursors_dir / name
            cur_dir.mkdir(parents=True, exist_ok=True)

            xhot = cfg.get("x_hotspot", DEFAULT_XHOT) / 256.0
            yhot = cfg.get("y_hotspot", DEFAULT_YHOT) / 256.0
            delay = cfg.get("x11_delay", DEFAULT_DELAY)

            meta_lines = [
                "resize_algorithm = bilinear",
                f"hotspot_x = {xhot:.6f}",
                f"hotspot_y = {yhot:.6f}",
                "",
            ]

            png_pattern = cfg["png"]
            if "*" in png_pattern:
                prefix = png_pattern.replace("-*.png", "")
                matching = sorted([k for k in svg_map if k.startswith(prefix + "-") and k.endswith(".svg")])
                for frame in matching:
                    (cur_dir / frame).write_text(svg_map[frame], encoding="utf-8")
                    meta_lines.append(f"define_size = 0, {frame}, {delay}")
            else:
                svg_name = png_pattern.replace(".png", ".svg")
                if svg_name in svg_map:
                    (cur_dir / svg_name).write_text(svg_map[svg_name], encoding="utf-8")
                    meta_lines.append(f"define_size = 0, {svg_name}")

            for sym in cfg.get("symlinks", []):
                meta_lines.append(f"define_override = {sym}")

            (cur_dir / "meta.hl").write_text("\n".join(meta_lines) + "\n", encoding="utf-8")

        # Compile with hyprcursor-util
        out_dir = Path(tmpdir) / "theme_Bibata-Caelestia"
        res = subprocess.run(
            ["hyprcursor-util", "--create", str(src_dir)],
            cwd=tmpdir,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            check=False,
        )
        if res.returncode == 0 and out_dir.exists():
            try:
                (target_dir / "manifest.hl").write_text(
                    (out_dir / "manifest.hl").read_text(encoding="utf-8"), encoding="utf-8"
                )
                dst_hcursors = target_dir / "hyprcursors"
                if dst_hcursors.exists():
                    shutil.rmtree(dst_hcursors)
                shutil.copytree(out_dir / "hyprcursors", dst_hcursors)
            except Exception:
                pass


SOBER_CONFIG = {
    "ArrowFarCursor": {
        "svg": "left_ptr.svg",
        "rel_path": "Cursors/KeyboardMouse/ArrowFarCursor.png",
        "x_hotspot": 65.0,
        "y_hotspot": 14.0,
    },
    "ArrowCursor": {
        "svg": "hand2.svg",
        "rel_path": "Cursors/KeyboardMouse/ArrowCursor.png",
        "x_hotspot": 113.5,
        "y_hotspot": 13.0,
    },
    "IBeamCursor": {
        "svg": "xterm.svg",
        "rel_path": "Cursors/KeyboardMouse/IBeamCursor.png",
        "x_hotspot": 128.0,
        "y_hotspot": 128.0,
    },
    "MouseLockedCursor": {
        "svg": "crosshair.svg",
        "rel_path": "MouseLockedCursor.png",
        "x_hotspot": 128.0,
        "y_hotspot": 128.0,
    },
}


def is_sober_installed(home: Path) -> bool:
    sober_dir = home / ".var/app/org.vinegarhq.Sober"
    if not sober_dir.is_dir():
        return False

    if shutil.which("flatpak"):
        try:
            res = subprocess.run(
                ["flatpak", "info", "org.vinegarhq.Sober"],
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
                check=False,
            )
            return res.returncode == 0
        except Exception:
            pass
    return True


def build_sober_cursors(svg_map: dict[str, str], cursor_size: int = 24) -> None:
    # 1:1 exact match with desktop cursor size
    auto_render_size = cursor_size

    for home in get_possible_user_homes():
        if not is_sober_installed(home):
            continue

        sober_base = home / ".var/app/org.vinegarhq.Sober/data/sober/asset_overlay/content/textures"

        for item_name, cfg in SOBER_CONFIG.items():
            svg_file = cfg["svg"]
            if svg_file not in svg_map:
                continue

            out_path = sober_base / cfg["rel_path"]
            render_size = cfg.get("render_size", auto_render_size)
            scale = render_size / 256.0

            x_hot = cfg.get("x_hotspot", DEFAULT_XHOT)
            y_hot = cfg.get("y_hotspot", DEFAULT_YHOT)

            # Center the exact active click tip/hotspot at (32, 32) in the 64x64 canvas
            offset_x = cfg.get("offset_x", 32.0 - (x_hot * scale))
            offset_y = cfg.get("offset_y", 32.0 - (y_hot * scale))

            try:
                handle = Rsvg.Handle.new_from_data(svg_map[svg_file].encode("utf-8"))
                surf = cairo.ImageSurface(cairo.FORMAT_ARGB32, 64, 64)
                cr = cairo.Context(surf)
                cr.translate(offset_x, offset_y)
                cr.scale(scale, scale)
                handle.render_cairo(cr)
                surf.flush()

                out_path.parent.mkdir(parents=True, exist_ok=True)
                surf.write_to_png(str(out_path))
            except Exception as e:
                print(f"Warning: Failed to render Sober cursor {item_name}: {e}", file=sys.stderr)


def write_theme_to_dir(target_dir: Path, built_cursors: dict[str, bytes], svg_map: dict[str, str]) -> None:
    cursors_dir = target_dir / "cursors"
    try:
        cursors_dir.mkdir(parents=True, exist_ok=True)
    except Exception:
        return

    index_theme = (
        "[Icon Theme]\n"
        "Name=Bibata-Caelestia\n"
        "Comment=Bibata cursor themed dynamically with Caelestia\n"
        'Inherits="core"\n'
    )
    cursor_theme = "[Icon Theme]\nInherits=Bibata-Caelestia\n"

    try:
        (target_dir / "index.theme").write_text(index_theme, encoding="utf-8")
        (target_dir / "cursor.theme").write_text(cursor_theme, encoding="utf-8")
    except Exception:
        pass

    for name, data in built_cursors.items():
        try:
            (cursors_dir / name).write_bytes(data)
        except Exception as e:
            print(f"Warning: Failed to write {name}: {e}", file=sys.stderr)

    for name, cfg in CURSOR_CONFIG.items():
        if name in built_cursors:
            for symlink in cfg.get("symlinks", []):
                link_path = cursors_dir / symlink
                try:
                    if link_path.is_symlink() or link_path.exists():
                        link_path.unlink()
                    link_path.symlink_to(name)
                except Exception:
                    pass

    # Build scalable Hyprcursor theme
    build_hyprcursor_theme(svg_map, target_dir)


def main():
    parser = argparse.ArgumentParser(description="Build Bibata-Caelestia cursor theme")
    parser.add_argument(
        "--dest",
        default="/usr/share/icons/Bibata-Caelestia",
        help="Target theme installation path (default: /usr/share/icons/Bibata-Caelestia)",
    )
    parser.add_argument(
        "--size",
        type=int,
        default=None,
        help="Cursor size to apply (default: auto-detect from config)",
    )
    args = parser.parse_args()

    applied_size = args.size if args.size is not None else detect_cursor_size()

    t0 = time.perf_counter()
    dest_path = Path(args.dest)

    # Determine target directories (both system and user icons)
    target_dirs: list[Path] = []
    if is_dir_writable(dest_path / "cursors"):
        target_dirs.append(dest_path)
    elif os.geteuid() != 0:
        # Attempt sudo if available
        res = subprocess.run(["sudo", "-n", sys.executable, __file__, *sys.argv[1:]])
        if res.returncode == 0:
            return

    # Always ensure user icon directories receive the build
    for home in get_possible_user_homes():
        user_icons = home / ".local/share/icons/Bibata-Caelestia"
        if is_dir_writable(user_icons / "cursors") and user_icons not in target_dirs:
            target_dirs.append(user_icons)

    if not target_dirs:
        # Fallback to creating user icons
        for home in get_possible_user_homes():
            user_icons = home / ".local/share/icons/Bibata-Caelestia"
            try:
                (user_icons / "cursors").mkdir(parents=True, exist_ok=True)
                target_dirs.append(user_icons)
                break
            except Exception:
                continue

    svg_map = find_svg_sources()
    if not svg_map:
        print("Error: No SVGs found to build cursors!", file=sys.stderr)
        sys.exit(1)

    built_cursors = {}
    with concurrent.futures.ThreadPoolExecutor() as executor:
        futures = {
            executor.submit(build_single_cursor, name, cfg, svg_map, FALLBACK_SIZES): name
            for name, cfg in CURSOR_CONFIG.items()
        }
        for future in concurrent.futures.as_completed(futures):
            name, data = future.result()
            if data:
                built_cursors[name] = data

    # Write to all target locations (e.g. system and user icon dirs)
    for tdir in target_dirs:
        write_theme_to_dir(tdir, built_cursors, svg_map)

    # Render Sober cursor overlay if Sober is installed
    build_sober_cursors(svg_map, applied_size)

    # Reload cursors live across all subsystems (Hyprland, XWayland/X11, GTK)
    reload_system_cursors("Bibata-Caelestia", applied_size)

    t1 = time.perf_counter()
    dest_str = ", ".join(str(d) for d in target_dirs)
    print(f"Successfully built and reloaded Bibata-Caelestia (size {applied_size}) with {len(built_cursors)} cursors in {t1 - t0:.3f}s -> {dest_str}")


if __name__ == "__main__":
    main()
