"""A sound server is not needed to collect these tests.

Importing sounddevice initializes PortAudio, which raises when no
PulseAudio or ALSA server is reachable (CI has none). The modules under
test import it at module scope, so a stub keeps collection working. The
tests that exercise audio behaviour replace the parts they use.
"""
import sys
from unittest.mock import MagicMock

try:
    import sounddevice  # noqa: F401
except Exception:       # no audio server here; the stub is enough
    _stub = MagicMock()
    _stub.PortAudioError = type("PortAudioError", (Exception,), {})
    sys.modules["sounddevice"] = _stub
