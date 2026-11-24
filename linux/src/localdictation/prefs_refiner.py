"""The optional Phonon drafter download and its Preferences switch."""
from gi.repository import Gtk

from . import ai_download
from .download_progress_dialog import DownloadTask, run_downloads
from .ui_style import show_message


def acceleration_option(prefs):
    """Acceleration is opt-in and never required for ordinary refinement."""
    check = Gtk.CheckButton(label="Accelerate Phonon refinement (experimental)")
    check.set_active(bool(prefs.config.get("refiner_acceleration", False)))
    check.set_tooltip_text(
        "Downloads an extra 215 MB for Phonon. Speed depends on your hardware; "
        "turn this off if refinement is slower. Other refiner models are unchanged.")

    def toggled(button):
        if not button.get_active():
            prefs.update_config("refiner_acceleration", False)
            return
        if ai_download.drafter_path("phonon") is None:
            response = show_message(
                prefs.window, Gtk.MessageType.QUESTION, "Download Phonon acceleration?",
                "This adds a one-time 215 MB download. Everything runs on this computer.\n\n"
                "The ordinary refiner is used if acceleration cannot start.",
                [("Cancel", Gtk.ResponseType.CANCEL), ("Download", Gtk.ResponseType.OK)],
                default=Gtk.ResponseType.OK)
            result = response == Gtk.ResponseType.OK and run_downloads(
                prefs.window, "Downloading Phonon acceleration",
                "One-time download. Everything runs on this computer.",
                [DownloadTask("Phonon acceleration", ai_download.DRAFTER_SIZE_TEXT,
                              ai_download.make_drafter_download_func())],
                arrived=lambda: ai_download.drafter_path("phonon") is not None)
            if not result:
                prefs._untick_ai_feature(button, "refiner_acceleration", toggled)
                return
        prefs.update_config("refiner_acceleration", True)

    check.connect("toggled", toggled)
    return check
