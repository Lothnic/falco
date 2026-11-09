"""Small, explicit bridge between the Rune window and the dictation service.

Requests are JSON on stdin and replies are JSON on stdout. Dictated text is
never placed in command-line arguments or logs.
"""
import json
import subprocess
import sys

from . import ai_download, config, custom_words, history
from .dbus_service import DBUS_INTERFACE, DBUS_NAME, DBUS_PATH


def _service():
    import dbus
    bus = dbus.SessionBus()
    obj = bus.get_object(DBUS_NAME, DBUS_PATH, introspect=False)
    return dbus.Interface(obj, DBUS_INTERFACE)


def snapshot():
    cfg = config.load_config()
    data = {
        "connected": False,
        "running": False,
        "recording": False,
        "engine": "",
        "error": "",
        "hotkey": cfg.hotkey or "Not set",
        "toggle_hotkey": cfg.toggle_hotkey or "Not set",
        "microphone": cfg.mic or "System default",
        "model": cfg.model,
        "refiner": bool(cfg.ai_corrections),
        "refiner_installed": ai_download.is_installed(),
        "auto_space": bool(cfg.auto_space),
        "auto_period": bool(cfg.auto_period),
        "words": custom_words.load(),
        "recent": history.get_entries(),
    }
    try:
        status = _service().GetStatus(timeout=1.5)
        data.update(connected=True, running=bool(status.get("service_running")),
                    recording=bool(status.get("recording")),
                    engine=str(status.get("engine", "")))
    except Exception:
        data["error"] = "Dictation service is not available. Open Phonon Linux from your apps."
    return data


def execute(request):
    action = request.get("action", "snapshot")
    if action == "snapshot":
        return snapshot()
    if action in ("start_service", "stop_service"):
        service = _service()
        if action == "start_service":
            service.StartService(timeout=2)
        else:
            service.StopService(timeout=2)
        return {"ok": True}
    if action in ("settings", "words"):
        cmd = [sys.executable, "-m", f"{__package__}.prefs"]
        if action == "words":
            cmd.append("--tab=words")
        subprocess.Popen(cmd, stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL,
                         stderr=subprocess.DEVNULL, start_new_session=True)
        return {"ok": True}
    if action == "add_word":
        from . import vocabulary
        word = request.get("word")
        if not isinstance(word, str):
            raise ValueError("Enter a word or short name.")
        vocabulary.save_word(word, [])
        return {"ok": True}
    if action == "set_option":
        name = request.get("name")
        value = request.get("value")
        if name not in ("auto_space", "auto_period") or not isinstance(value, bool):
            raise ValueError("Unknown setting.")
        settings = config.load_config()
        setattr(settings, name, value)
        config.save_config(settings)
        return {"ok": True}
    if action == "copy":
        from .clipboard import copy_text
        text = request.get("text")
        if not isinstance(text, str) or not copy_text(text):
            raise RuntimeError("Couldn't copy the dictation to the clipboard.")
        return {"ok": True}
    raise ValueError("Unknown action")


def main():
    try:
        request = json.load(sys.stdin)
        response = execute(request)
    except Exception as exc:
        # The error is displayed to the user; avoid including transcript text.
        response = {"ok": False, "error": str(exc) or "The action failed."}
    print(json.dumps(response, ensure_ascii=False))


if __name__ == "__main__":
    main()
