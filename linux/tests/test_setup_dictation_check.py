import shutil
import subprocess
import time
from types import SimpleNamespace

import gi
import pytest

gi.require_version("Gdk", "3.0")
gi.require_version("Gtk", "3.0")
gi.require_version("GdkX11", "3.0")
from gi.repository import Gdk, GdkX11, Gtk

from localdictation.dbus_service import TuxTalkDBusService
from localdictation.setup_dictation_check import DictationCheck
from localdictation.tray_dbus_app import TrayAppInstance


def drain_gtk():
    while Gtk.events_pending():
        Gtk.main_iteration_do(False)


@pytest.fixture
def check():
    Gtk.init_check([])
    if not isinstance(Gdk.Display.get_default(), GdkX11.X11Display) or not shutil.which("xdotool"):
        pytest.skip("The setup field test needs an X11 display and xdotool")

    window = Gtk.Window()
    box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL)
    window.add(box)
    check = DictationCheck(box, False, lambda: True)
    window.show_all()
    check.entry.grab_focus()
    Gdk.Display.get_default().sync()
    drain_gtk()
    try:
        subprocess.run(["xdotool", "windowfocus", "--sync", str(window.get_window().get_xid())],
                       check=True, timeout=5)
        drain_gtk()
        assert check.entry.has_focus()
        check.start()
        check._refresh()
        yield check
    finally:
        check.stop()
        window.destroy()
        drain_gtk()


def test_setup_verifies_text_arrives_in_the_field(check, monkeypatch):
    relay = TuxTalkDBusService.__new__(TuxTalkDBusService)
    relay.app = TrayAppInstance(SimpleNamespace(dictation_check=check))
    monkeypatch.setattr(relay, "RecordingStateChanged", lambda _recording: None)

    attempt = relay.NotifyRecordingState(True)
    assert relay.DictationCheckHasFocus(attempt)
    assert check.phase == "listening"
    relay.NotifyRecordingState(False)
    assert check.phase == "processing"
    relay.NotifyDictationCheck(attempt, "typed")
    assert check.phase == "waiting_for_text"

    subprocess.run(["xdotool", "type", "--delay", "0", "This is my first dictation."],
                   check=True, timeout=5)
    # XTest delivery is asynchronous: xdotool can exit before GTK has any
    # pending events, especially after the other window tests have run.
    deadline = time.monotonic() + 2
    while check.entry.get_text() != "This is my first dictation." and time.monotonic() < deadline:
        drain_gtk()
        time.sleep(0.005)
    assert check.entry.get_text() == "This is my first dictation."
    assert check.phase == "verified"

    newer_attempt = relay.NotifyRecordingState(True)
    relay.NotifyDictationCheck(attempt, "microphone")
    assert check.phase == "listening"
    assert not relay.DictationCheckHasFocus(attempt)
    assert relay.DictationCheckHasFocus(newer_attempt)
    check.stop()
    assert not relay.DictationCheckHasFocus(newer_attempt)


def test_setup_gives_step_specific_help(check):
    check.report(0, "microphone")
    assert check.preferences_tab == "audio"

    attempt = check.recording_changed(True)
    check.recording_changed(False)
    check.report(attempt, "typed")
    check.deadline = 1
    check._refresh()
    assert check.preferences_tab == "advanced"
    assert "Text didn't reach" in check.status.get_text()
