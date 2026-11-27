"""TuxTalk - voice dictation for Linux"""

# The upstream TalkType->TuxTalk folder migration (rename_migration.py) is
# imported on demand by the tray and the uninstaller, not here: this fork
# must never migrate an existing TuxTalk install, so nothing runs at import.
MIGRATION_LOG = []

import ctypes.util  # noqa: E402
import os  # noqa: E402

__version__ = "2.6.1"

# Where the AppImage (and the .deb/.rpm made from it) keeps its own PortAudio:
# <root>/usr/src/tuxtalk/ -> <root>/usr/lib/portaudio/. In a dev checkout or
# the Flatpak this folder doesn't exist and nothing changes.
_BUNDLED_PORTAUDIO_DIR = os.path.join(
    os.path.dirname(os.path.abspath(__file__)), os.pardir, os.pardir, "lib", "portaudio")


def _use_bundled_portaudio(lib_dir=_BUNDLED_PORTAUDIO_DIR):
    """Let sounddevice fall back to the bundled PortAudio.

    sounddevice finds PortAudio with ctypes.util.find_library("portaudio"),
    which only consults the system's linker cache, so a copy inside the
    AppImage is invisible to it and a system without libportaudio would have
    no microphone at all.

    The system's PortAudio still wins when there is one. Runs on package
    import, which is always before sounddevice is imported.
    """
    bundled = os.path.join(lib_dir, "libportaudio.so.2")
    if not os.path.isfile(bundled):
        return
    system_find_library = ctypes.util.find_library

    def find_library(name):
        found = system_find_library(name)
        if found is None and name == "portaudio":
            return os.path.normpath(bundled)
        return found

    ctypes.util.find_library = find_library


_use_bundled_portaudio()
