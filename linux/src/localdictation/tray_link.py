"""The dictation service's side of its D-Bus link to the tray: telling it
when recording starts and stops and when a hotkey is pressed, and asking it
to show the voice commands. The tray re-sends these to the GNOME extension.
Every call has a short time limit: a busy or missing tray must never hold
up a dictation."""
from . import focused_window
from .logger import setup_logger

logger = setup_logger(__name__)


def call(method: str, *args, what: str, signature: str | None = None):
    """Call the tray's D-Bus *method* with *args*. A failure, dbus itself
    missing included, is logged as "Could not {what}" and never raised.

    Every call has the short time limit focused_window.TRAY_TIMEOUT_S: some
    are made with every keyboard exclusively grabbed. Arguments that aren't
    plain strings or booleans need their D-Bus *signature* ("u" for a
    process id, "as" for a list of strings); without one dbus-python
    guesses from the Python values.

    Each call goes to the well-known name, so the bus delivers it to
    whichever tray holds it now: a service that outlived a crashed tray
    reaches the one opened again. A blocking call needs no main loop, so it
    also works when something else made the shared session bus without one
    (an early notification); a proxy that follows the name refuses then.
    """
    try:
        import dbus
        from .dbus_service import DBUS_INTERFACE, DBUS_NAME, DBUS_PATH
        return dbus.SessionBus().call_blocking(
            DBUS_NAME, DBUS_PATH, DBUS_INTERFACE, method,
            signature, args, timeout=focused_window.TRAY_TIMEOUT_S)
    except Exception as e:
        logger.info(f"Could not {what}: {e}")


def notify_recording_state(is_recording: bool) -> int:
    """Tell the tray recording started or stopped. The tray owns the D-Bus
    name the GNOME extension listens to, and emits the signal for us."""
    return int(call("NotifyRecordingState", is_recording,
                    what="notify tray of recording state") or 0)


def notify_dictation_check(attempt: int, outcome: str) -> None:
    """Report a first-run test result without including audio or text."""
    call("NotifyDictationCheck", attempt, outcome, signature="us",
         what="report the dictation check result")


def dictation_check_has_focus(attempt: int) -> bool:
    return bool(call("DictationCheckHasFocus", attempt, signature="u",
                     what="check the practice field's focus"))


def notify_hotkey_pressed(key_name: str):
    """Tell the tray which dictation key was pressed during the hotkey test;
    its D-Bus service emits the HotkeyPressed signal Preferences listens for."""
    call("NotifyHotkeyPressed", key_name, what="notify tray of hotkey press")


def show_voice_commands():
    """Tell the tray to show the voice commands quick reference."""
    call("ShowVoiceCommands", what="show voice commands via D-Bus")
