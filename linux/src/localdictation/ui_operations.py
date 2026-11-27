"""Validated UI operations using the existing dictation, download and backup code."""
from dataclasses import asdict
import os

from . import ai_download, config, ui_settings
from .ui_jobs import Cancelled


def _check(cancel):
    if cancel.is_set():
        raise Cancelled()


def _download(factory, report, cancel):
    _check(cancel)
    if not factory(report, cancel):
        _check(cancel)
        raise RuntimeError("The download did not finish. Check your connection and retry.")


def download_models(candidate, changes, report, cancel, all_models=False):
    if all_models or {"model", "device"} & changes.keys():
        if candidate.model == "parakeet-v3":
            from .parakeet_ultra import make_download_func
            _download(make_download_func("vulkan" if candidate.device == "vulkan" else "cpu"), report, cancel)
        elif candidate.device == "vulkan":
            from . import whisper_vulkan
            _download(whisper_vulkan.make_engine_download_func(candidate.model), report, cancel)
            _download(whisper_vulkan.make_model_download_func(candidate.model), report, cancel)
        else:
            from .model_helper import make_model_download_func
            if candidate.device == "cuda":
                from .cuda_download import download_cuda_libraries
                _download(download_cuda_libraries, report, cancel)
            _download(make_model_download_func(candidate.model), report, cancel)
    refiner_changes = {"ai_corrections", "voice_editing", "command_mode", "refiner_model", "refiner_acceleration", "language"}
    if (all_models or refiner_changes & changes.keys()) and (candidate.ai_corrections or candidate.voice_editing or candidate.command_mode):
        model = ai_download.selected_model(candidate)
        _download(ai_download.make_engine_download_func(), report, cancel)
        _download(ai_download.make_model_download_func(model), report, cancel)
        if model == "phonon" and candidate.refiner_acceleration:
            _download(ai_download.make_drafter_download_func(), report, cancel)


def save_settings(changes, report, cancel):
    before = config.load_config()
    candidate = ui_settings.checked_changes(before, changes)
    download_models(candidate, changes, report, cancel)
    _check(cancel)
    # Read again after a potentially long download so unrelated live changes survive.
    fresh = config.load_config()
    candidate = ui_settings.checked_changes(fresh, changes)
    if "launch_at_login" in changes:
        from .autostart import set_autostart
        if not set_autostart(candidate.launch_at_login):
            raise RuntimeError("Your desktop could not change launch at login. Settings were not saved.")
    try:
        config.save_config(candidate)
    except Exception:
        if "launch_at_login" in changes:
            set_autostart(fresh.launch_at_login)
        raise
    changed = {k for k in asdict(candidate) if getattr(fresh, k) != getattr(candidate, k)}
    if config.needs_service_restart(changed):
        report("Settings saved. Restarting dictation…", 95)
        from .ui_bridge import _service
        try:
            _service().RestartIfOn(timeout=2)
        except Exception:
            return {"message": "Settings saved. Start dictation to use the new setup."}
    return {"message": "Settings saved."}


def perform(kind, payload, report, cancel):
    if kind == "setup_keyboard":
        from . import secure_input
        report("Waiting for your desktop to approve typing access…", 20)
        ok, message = secure_input.install_with_pkexec()
        if not ok:
            raise RuntimeError(message or "Typing setup was not completed.")
        return {"message": "Typing access is ready. Restart dictation to use it."}
    if kind == "hotkey_test":
        import time
        import dbus.mainloop.glib
        from gi.repository import GLib
        from .prefs_hotkey_test import _hearing_hotkeys, _test_mode
        from .ui_bridge import _service
        if not _service().GetStatus(timeout=2).get("service_running"):
            raise ValueError("Start dictation first, then test its saved shortcuts.")
        dbus.mainloop.glib.DBusGMainLoop(set_as_default=True)
        heard = set()

        def on_key(key):
            heard.add(str(key))
            report("Working: " + ", ".join(sorted(heard)) + ". Keep testing or cancel to finish.", 50)

        report("Press your saved hold and toggle shortcuts. Dictation is paused for this 10-second test.", 10)
        with _hearing_hotkeys(on_key), _test_mode():
            deadline = time.monotonic() + 10
            context = GLib.MainContext.default()
            while time.monotonic() < deadline:
                _check(cancel)
                while context.pending():
                    context.iteration(False)
                time.sleep(0.05)
        return {"message": ("Shortcuts heard: " + ", ".join(sorted(heard)) + ". Dictation resumed."
                            if heard else "No shortcuts heard. Check typing access and try again. Dictation resumed.")}
    if kind == "save_settings":
        return save_settings(payload["changes"], report, cancel)
    if kind == "download_models":
        download_models(config.load_config(), {}, report, cancel, all_models=True)
        _check(cancel)
        return {"message": "Selected models are ready."}
    if kind == "check_updates":
        from . import update_checker
        report("Checking GitHub for an update…", 10)
        result = update_checker.check_for_updates()
        if not result.get("release"):
            raise RuntimeError("Could not check for updates. Check your internet connection and retry.")
        return {"message": (f"Falco {result['latest_version']} is available." if result.get("update_available")
                            else "You have the latest version."),
                "update_available": bool(result.get("update_available")),
                "release_url": result["release"].get("html_url", "")}
    if kind == "install_update":
        from . import self_update
        if not self_update.is_managed_install():
            raise RuntimeError("Update this copy with its package manager or the installer from falco.lothnic.dev.")
        report("Looking up the latest release…", 5)
        from .update_checker import fetch_latest_release
        release = fetch_latest_release()
        if not release:
            raise RuntimeError("Could not look up the latest release.")
        _check(cancel)
        ok, message = self_update.install(release["tag_name"], lambda text, percent=50: report(text, percent))
        if not ok:
            raise RuntimeError(message)
        return {"message": "Update installed. Quit and reopen Falco to use it."}
    if kind == "backup":
        from . import settings_backup
        path = payload.get("path", "")
        if not isinstance(path, str) or not os.path.isabs(path):
            raise ValueError("Choose an absolute file path for the backup.")
        if os.path.exists(path):
            raise ValueError("This file already exists. Choose another name.")
        settings_backup.write_backup(path)
        return {"message": "Settings backup saved."}
    if kind == "restore":
        from . import settings_backup
        if payload.get("confirmed") is not True:
            raise ValueError("Confirm that you want to replace your current settings.")
        backup = settings_backup.read_backup(payload["path"])
        _check(cancel)
        notes = settings_backup.restore(backup)
        return {"message": "Settings restored. Restart dictation to apply the restored setup." +
                (" " + " ".join(notes) if notes else "")}
    if kind == "microphone_test":
        import sounddevice as sd
        import numpy as np
        from .microphones import find_input_device
        candidate = config.load_config()
        index = find_input_device(candidate.mic)
        rate = int(sd.query_devices(index, "input")["default_samplerate"])
        report("Listening for three seconds. Say a short sentence…", 20)
        recording = sd.rec(int(rate * 3), samplerate=rate, channels=1, dtype="float32", device=index)
        sd.wait()
        level = float(np.max(np.abs(recording)))
        return {"message": ("Microphone heard audio. You’re ready to dictate." if level > 0.005
                            else "Very little audio was heard. Check the microphone and input volume.")}
    raise ValueError("Unknown operation.")
