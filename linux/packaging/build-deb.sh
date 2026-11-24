#!/usr/bin/env bash
# Build Falco's .deb: a system-wide install under /usr that the receiving
# machine's package manager owns, so upgrades and removal go through apt.
#
#   ./packaging/build-deb.sh [--with-rune]
#
# The .deb carries the Python source and a virtual environment built against
# the system's Python, the way install.sh's per-user install does. The system
# packages it needs (GTK 3, python3-gi, PortAudio, ...) are declared as
# dependencies, so apt refuses the install with a clear list rather than the
# app failing to start.
#
# Write to dist/ next to this repository's linux/ directory. Needs dpkg-deb
# and fakeroot; needs no root.
set -euo pipefail

source_dir="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/.." && pwd)"
out_dir="$(realpath -m -- "${FALCO_DEB_OUT:-$source_dir/dist}")"
with_rune=0
for arg in "$@"; do
    case "$arg" in
        --with-rune) with_rune=1 ;;
        -h|--help) sed -n '2,14p' "${BASH_SOURCE[0]}" | sed 's/^# \{0,1\}//'; exit 0 ;;
        *) printf 'Unknown option: %s\n' "$arg" >&2; exit 2 ;;
    esac
done

for tool in dpkg-deb fakeroot; do
    command -v "$tool" >/dev/null 2>&1 ||
        { printf 'Missing %s; install it to build the package.\n' "$tool" >&2; exit 1; }
done
for module in gi dbus; do
    /usr/bin/python3 -c "import $module" 2>/dev/null ||
        { printf 'Missing system Python module %s; see linux/README.md.\n' "$module" >&2; exit 1; }
done

version="$(sed -n 's/^version = "\([0-9A-Za-z][0-9A-Za-z.+-]*\)"$/\1/p' "$source_dir/pyproject.toml")"
[[ "$version" =~ ^[0-9A-Za-z][0-9A-Za-z.+-]*$ ]] ||
    { printf 'Could not read the Falco package version from pyproject.toml.\n' >&2; exit 1; }
# The venv inside carries compiled wheels for this machine's interpreter and
# architecture, so the package is not `all` and not portable across them.
architecture="$(dpkg --print-architecture)"

work="$(mktemp -d)"
trap 'rm -rf -- "$work"' EXIT
pkg="$work/falco"
install -d "$pkg/DEBIAN" \
    "$pkg/usr/lib/falco" \
    "$pkg/usr/bin" \
    "$pkg/usr/share/applications" \
    "$pkg/usr/share/doc/falco"

# --- the application ---------------------------------------------------------
cp -a "$source_dir/src" "$source_dir/pyproject.toml" "$source_dir/README.md" \
    "$source_dir/LICENSE" "$pkg/usr/lib/falco/"
# Built at its final path: a venv stores absolute paths and would otherwise
# point into this temporary directory.
/usr/bin/python3 -m venv --system-site-packages "$pkg/usr/lib/falco/.venv"
if command -v uv >/dev/null 2>&1; then
    uv pip install --quiet --python "$pkg/usr/lib/falco/.venv/bin/python" "$pkg/usr/lib/falco"
else
    "$pkg/usr/lib/falco/.venv/bin/python" -m pip install --quiet "$pkg/usr/lib/falco"
fi

if [[ "$with_rune" == 1 ]]; then
    install -D -m 644 "$source_dir/rune-overlay/target/release/VERSION" "$pkg/usr/lib/falco/bin/VERSION"
    for binary in phonon-overlay phonon-window; do
        built="$source_dir/rune-overlay/target/release/$binary"
        [[ -x "$built" ]] ||
            { printf 'Missing %s; build Rune first (see linux/README.md).\n' "$built" >&2; exit 1; }
        install -D -m 755 "$built" "$pkg/usr/lib/falco/bin/$binary"
    done
fi

# The launcher: the same process install.sh's run.sh starts, without DEV_MODE,
# so the app knows it is a package install and its data folder is the usual one.
cat > "$pkg/usr/lib/falco/run.sh" <<'RUNNER'
#!/usr/bin/env bash
set -e
release_dir="/usr/lib/falco"
if [[ "${FALCO_LEGACY_UI:-0}" != 1 && -x "$release_dir/bin/phonon-overlay" ]]; then
    export PHONON_RUNE_OVERLAY="${PHONON_RUNE_OVERLAY:-$release_dir/bin/phonon-overlay}"
fi
exec "$release_dir/.venv/bin/python" -m localdictation.cli "$@"
RUNNER
chmod 755 "$pkg/usr/lib/falco/run.sh"

cat > "$pkg/usr/bin/falco" <<'LAUNCHER'
#!/usr/bin/env bash
set -e
release_dir="/usr/lib/falco"
# Commands stay usable from scripts even when the dashboard is installed.
if (($#)) || [[ "${FALCO_LEGACY_UI:-0}" == 1 ]]; then
    exec "$release_dir/run.sh" "$@"
fi
if [[ -x "$release_dir/bin/phonon-window" ]]; then
    if ! "$release_dir/.venv/bin/python" -c 'import dbus,sys; sys.exit(0 if dbus.SessionBus().name_has_owner("local.PhononLinux.App") else 1)' 2>/dev/null; then
        "$release_dir/run.sh" </dev/null >/dev/null 2>&1 &
    fi
    export PHONON_PYTHON="$release_dir/.venv/bin/python"
    export PHONON_BRIDGE_MODULE=localdictation.ui_bridge
    exec "$release_dir/bin/phonon-window" "$@"
fi
exec "$release_dir/run.sh" "$@"
LAUNCHER
chmod 755 "$pkg/usr/bin/falco"

# --- desktop entry and docs --------------------------------------------------
cat > "$pkg/usr/share/applications/falco.desktop" <<'DESKTOP'
[Desktop Entry]
Type=Application
Name=Falco
Comment=Local voice dictation and transcript cleanup
Exec=/usr/bin/falco
Icon=audio-input-microphone
Terminal=false
Categories=Utility;Accessibility;
StartupNotify=false
DESKTOP
chmod 644 "$pkg/usr/share/applications/falco.desktop"

install -m 644 "$source_dir/README.md" "$pkg/usr/share/doc/falco/README.md"
install -m 644 "$source_dir/LICENSE" "$pkg/usr/share/doc/falco/copyright"

# --- control files -----------------------------------------------------------
installed_size="$(du -sk --exclude=DEBIAN "$pkg" | cut -f1)"
cat > "$pkg/DEBIAN/control" <<CONTROL
Package: falco
Version: $version
Section: utils
Priority: optional
Architecture: $architecture
Installed-Size: $installed_size
Depends: python3 (>= 3.10), python3-venv, python3-gi, python3-gi-cairo, python3-cairo, python3-dbus, gir1.2-gtk-3.0, gir1.2-ayatanaappindicator3-0.1, libportaudio2, wl-clipboard
Recommends: xdotool, xclip
Maintainer: Falco contributors
Description: Local voice dictation for Linux
 Hold a key, speak, and Falco types into the focused application.
 Speech recognition and the optional transcript cleanup run on the
 machine; models are downloaded once. Nothing is sent anywhere, and no
 account is needed.
CONTROL
chmod 644 "$pkg/DEBIAN/control"

# A running copy keeps the old files in memory and its launcher in place, so an
# upgrade stops it first. Its settings and downloaded models are the user's and
# stay where they are: the package owns none of them.
cat > "$pkg/DEBIAN/preinst" <<'PREINST'
#!/bin/sh
set -e
pkill -u "$(id -u)" -f 'localdictation\.\(tray\|cli\)' 2>/dev/null || true
exit 0
PREINST

cat > "$pkg/DEBIAN/postinst" <<'POSTINST'
#!/bin/sh
set -e
# The command is new or changed: refresh the desktop database if it is here.
if command -v update-desktop-database >/dev/null 2>&1; then
    update-desktop-database -q /usr/share/applications 2>/dev/null || true
fi
exit 0
POSTINST

cat > "$pkg/DEBIAN/prerm" <<'PRERM'
#!/bin/sh
set -e
pkill -u "$(id -u)" -f 'localdictation\.\(tray\|cli\)' 2>/dev/null || true
exit 0
PRERM
chmod 755 "$pkg/DEBIAN/preinst" "$pkg/DEBIAN/postinst" "$pkg/DEBIAN/prerm"

install -d "$out_dir"
deb="$out_dir/falco_${version}_${architecture}.deb"
fakeroot dpkg-deb --build --root-owner-group "$pkg" "$deb" >/dev/null
printf 'Built %s\n' "$deb"
printf 'Install it with: sudo apt install %s\n' "$deb"
