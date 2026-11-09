"""Optional Rune recording overlay, with the existing indicator as a fallback.

The Rust process owns only presentation. Audio and dictation remain in the
Python service; at most a normalized meter level crosses this pipe.
"""
import atexit
import os
import queue
import subprocess
import threading
import time

from gi.repository import GLib
from .logger import setup_logger

logger = setup_logger(__name__)


class RuneIndicator:
    """Use Rune when its overlay is available; keep GTK ready otherwise."""
    style = "orb"  # The Rune view needs RMS levels, not waveform or FFT data.

    def __init__(self, fallback, binary):
        self.fallback = fallback
        self._commands = queue.Queue()
        self._lock = threading.Lock()
        self._recording = False
        self._generation = 0
        self._checked_generation = -1
        self._available_generation = -1
        self._fallback_generation = -1
        self._last_level = 0.0
        env = os.environ.copy()
        # GNOME does not expose wlr-layer-shell; XWayland supplies Rune's
        # non-activating X11 overlay and preserves focus in the target app.
        if env.get("DISPLAY"):
            env["WINIT_UNIX_BACKEND"] = "x11"
        self.process = subprocess.Popen([binary], stdin=subprocess.PIPE,
                                        stdout=subprocess.PIPE, stderr=subprocess.DEVNULL,
                                        text=True, bufsize=1, env=env)
        threading.Thread(target=self._write_loop, daemon=True, name="phonon-rune-writer").start()
        threading.Thread(target=self._read_loop, daemon=True, name="phonon-rune-reader").start()
        atexit.register(self.close)

    def _send(self, command):
        if self.process.poll() is not None:
            return False
        try:
            self._commands.put_nowait(command)
            return True
        except queue.Full:
            return False

    def _write_loop(self):
        try:
            while True:
                command = self._commands.get()
                if command is None:
                    return
                self.process.stdin.write(command + "\n")
                self.process.stdin.flush()
        except (BrokenPipeError, OSError, ValueError):
            pass

    def _read_loop(self):
        try:
            for line in self.process.stdout:
                words = line.split()
                if len(words) == 2 and words[1].isdigit() and words[0] in ("Available", "Unavailable"):
                    generation = int(words[1])
                    with self._lock:
                        if self._generation == generation:
                            self._checked_generation = generation
                            if words[0] == "Available":
                                self._available_generation = generation
                    if words[0] == "Available":
                        GLib.idle_add(self._hide_fallback_if_current, generation)
                    else:
                        GLib.idle_add(self._restore_fallback_if_current, generation)
        finally:
            with self._lock:
                generation = self._generation
            GLib.idle_add(self._restore_fallback_if_current, generation)

    def _hide_fallback_if_current(self, generation):
        with self._lock:
            if (self._recording and self._generation == generation
                    and self._fallback_generation == generation):
                self._fallback_generation = -1
                self.fallback.hide_indicator()
        return False

    def _restore_fallback_if_current(self, generation):
        with self._lock:
            if (self._recording and self._generation == generation
                    and self._fallback_generation != generation):
                self._fallback_generation = generation
                self.fallback.show_at_position()
                self.fallback.start_recording()
        return False

    def _fallback_after_timeout(self, generation):
        with self._lock:
            should_restore = (self._recording and self._generation == generation
                              and self._available_generation != generation)
        if should_restore:
            self._restore_fallback_if_current(generation)
        return False

    def _check_availability(self, generation):
        with self._lock:
            if (not self._recording or self._generation != generation
                    or self._checked_generation == generation):
                return False
            return self._send(f"status {generation}")

    def show_at_position(self):
        with self._lock:
            self._recording = True
            self._generation += 1
            generation = self._generation
        if self._send("show"):
            GLib.timeout_add(100, self._check_availability, generation)
            GLib.timeout_add(2500, self._fallback_after_timeout, generation)
        else:
            self._restore_fallback_if_current(generation)

    def start_recording(self):
        # The fallback starts only if Rune is unavailable.
        pass

    def hide_indicator(self):
        with self._lock:
            self._recording = False
            self._generation += 1
        self._send("hide")
        self.fallback.hide_indicator()

    def begin_processing(self):
        """Show finishing only when a newer recording is not in progress."""
        with self._lock:
            if self._recording:
                return None
            self._generation += 1
            generation = self._generation
            if not self._send("show"):
                return None
            self._send("processing")
            return generation

    def end_processing(self, generation):
        """A completed older job must not hide a newer recording."""
        with self._lock:
            if generation is not None and not self._recording and self._generation == generation:
                self._generation += 1
                self._send("hide")

    def set_audio_level(self, level):
        self.fallback.set_audio_level(level)
        now = time.monotonic()
        if now - self._last_level >= 0.05:
            self._last_level = now
            self._send(f"level {max(0.0, min(1.0, level)):.3f}")

    def apply_settings(self, **settings):
        self.fallback.apply_settings(**settings)

    def close(self):
        self._send("quit")
        try:
            self._commands.put_nowait(None)
        except queue.Full:
            pass
