"""Check that the regular dictation service types into the setup window."""
import time

from gi.repository import GLib, Gtk

from .config import saved_hold_key

_PROBLEMS = {
    "microphone": ("Falco couldn't hear the microphone. Check the input in Preferences → Audio.",
                   "audio"),
    "no_speech": ("No speech recognized. Hold the shortcut until you finish speaking.", None),
    "transcription": ("Speech recognition failed. Check the model in Preferences → General.",
                      "general"),
    "typing": ("Text didn't reach this field. Focus it and check Typing setup in "
               "Preferences → Advanced.", "advanced"),
    "cancelled": ("Dictation cancelled. Try the sentence again.", None),
}


class DictationCheck:
    def __init__(self, box, is_flatpak, check_ready):
        self.check_ready = check_ready
        self.attempt = 0
        self.phase = "starting"
        self.deadline = time.monotonic() + 25
        self.preferences_tab = None
        self.initial_text = ""
        self.timer = None

        heading = Gtk.Label(xalign=0)
        heading.set_markup("<b>Try your first dictation</b>")
        box.pack_start(heading, False, False, 0)
        shortcut = "your hold-to-talk shortcut" if is_flatpak else saved_hold_key()
        instructions = Gtk.Label(
            label=f'Hold {shortcut} and say “This is my first dictation.” Then release.', xalign=0)
        instructions.set_line_wrap(True)
        box.pack_start(instructions, False, False, 0)

        self.entry = Gtk.Entry(placeholder_text="Your words will appear here")
        self.entry.get_accessible().set_name("Dictation test field")
        self.entry.connect("changed", self._check_text)
        box.pack_start(self.entry, False, False, 0)

        self.status = Gtk.Label(label="Starting speech recognition…", xalign=0)
        self.status.set_line_wrap(True)
        box.pack_start(self.status, False, False, 0)

    def start(self):
        self.timer = GLib.timeout_add(150, self._refresh)

    def stop(self):
        if self.timer is not None:
            GLib.source_remove(self.timer)
            self.timer = None

    def has_focus(self, attempt):
        return (self.timer is not None and 0 < attempt == self.attempt
                and self.entry.has_focus())

    def _show(self, phase, text, tab=None, timeout=0):
        self.phase = phase
        self.status.set_text(text)
        self.preferences_tab = tab
        self.deadline = time.monotonic() + timeout if timeout else 0

    def _refresh(self):
        if self.phase in ("starting", "startup_delayed") and self.check_ready():
            self._show("ready", "Ready when you are.", timeout=8)
        elif self.deadline and time.monotonic() >= self.deadline:
            if self.phase == "starting":
                self._show("startup_delayed", "Speech recognition is taking a while to start. "
                           "You can check the model in Preferences → General.", "general")
            elif self.phase == "ready":
                self._show("ready", "If the shortcut doesn't respond, check Typing setup in "
                           "Preferences → Advanced.", "advanced")
            elif self.phase == "processing":
                self._show("processing", "Still transcribing…")
            elif self.phase == "waiting_for_text":
                self.report(self.attempt, "typing")
        return True

    def recording_changed(self, recording):
        if recording and self.entry.has_focus():
            self.attempt += 1
            self.initial_text = self.entry.get_text()
            self._show("listening", "Listening… Release the shortcut when you finish.")
            return self.attempt
        if not recording and self.phase == "listening":
            self._show("processing", "Transcribing…", timeout=12)
        return 0

    def report(self, attempt, outcome):
        if attempt == 0:
            if outcome != "microphone" or not self.entry.has_focus():
                return
        elif attempt != self.attempt or self.phase == "verified":
            return
        if outcome == "typed":
            # The simulated keys and the service's result can arrive in
            # either order. Wait for the field itself to show text.
            self._show("waiting_for_text", "Checking text insertion…", timeout=2)
            self._check_text(self.entry)
        elif outcome in _PROBLEMS:
            self._show("problem", *_PROBLEMS[outcome])

    def _check_text(self, entry):
        text = entry.get_text()
        if self.phase == "waiting_for_text" and text.strip() and text != self.initial_text:
            self._show("verified", "Dictation worked. Your words appeared in the field.")
