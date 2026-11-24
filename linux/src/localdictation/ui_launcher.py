"""Route desktop and tray entry points into the same versioned Rune window."""
import os
from pathlib import Path
import subprocess
import sys

from . import __version__


def binary():
    explicit = os.environ.get("PHONON_UI_BINARY")
    if explicit and os.access(explicit, os.X_OK):
        return explicit
    candidates = [Path(sys.prefix).parent / "bin", Path.home() / ".local/share/falco-app/rune"]
    for directory in candidates:
        try:
            matches = (directory / "VERSION").read_text().strip() == __version__
        except OSError:
            matches = False
        executable = directory / "phonon-window"
        if matches and os.access(executable, os.X_OK):
            return str(executable)
    return None


def open_dashboard(page="settings", section=None):
    """The binary's private session socket raises an existing window if open."""
    if os.environ.get("FALCO_LEGACY_UI") == "1":
        return None
    executable = binary()
    if not executable:
        return None
    command = [executable, "--page", page]
    if section:
        command += ["--section", section]
    try:
        return subprocess.Popen(command, stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL,
                                stderr=subprocess.DEVNULL, start_new_session=True,
                                env={**os.environ, "PHONON_PYTHON": sys.executable,
                                     "PHONON_BRIDGE_MODULE": "localdictation.ui_bridge"})
    except OSError:
        return None
