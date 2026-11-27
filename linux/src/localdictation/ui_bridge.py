"""Small, explicit bridge between the Rune window and the dictation service.

Requests are JSON on stdin and replies are JSON on stdout. Dictated text is
never placed in command-line arguments or logs.
"""
import html
import re
import json
import sys

from . import __version__, ai_download, config, custom_words, history
from .dbus_service import DBUS_INTERFACE, DBUS_NAME, DBUS_PATH


def _service():
    import dbus
    bus = dbus.SessionBus()
    obj = bus.get_object(DBUS_NAME, DBUS_PATH, introspect=False)
    return dbus.Interface(obj, DBUS_INTERFACE)


def snapshot():
    from . import learned_words, refiner_offer, settings_backup, stats, ui_jobs, ui_settings, vocabulary
    cfg = config.load_config()
    data = {
        "version": __version__,
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
        "settings": ui_settings.catalog(cfg),
        "job": ui_jobs.status(),
        "refiner_offer": refiner_offer.eligible(cfg),
    }
    commands = config.load_custom_commands()
    rows, snippets = vocabulary.split_commands(data["words"], commands)
    data["word_rows"] = [dict(word=word, phrases=phrases) for word, phrases in rows]
    data["snippets"] = [dict(phrase=phrase, text=text) for phrase, text in snippets.items()]
    data["learned_words"] = learned_words.words()
    summary = stats.summary(stats.load(), typing_wpm=getattr(cfg, "typing_wpm", 40))
    data["stats_rows"] = []
    for period, prefix in (("today", "Today"), ("week", "Last 7 days"), ("all", "All time")):
        for field, label in (("words", "words"), ("dictations", "dictations"),
                             ("seconds", "time dictating"), ("saved", "estimated time saved")):
            value = summary[period][field]
            data["stats_rows"].append(dict(label=f"{prefix} · {label}",
                                          value=stats.format_duration(value) if field in ("seconds", "saved") else str(value)))
    data["stats_rows"].extend([dict(label="Current streak", value=f"{summary['streak']} days"),
                               dict(label="Speaking pace", value=f"{summary['wpm']} words/min" if summary['wpm'] else "Not enough dictation yet")])
    data["restore_points"] = [dict(label=settings_backup.when_label(point.when), path=point.path)
                              for point in settings_backup.restore_points()]
    from . import commands_reference, secure_input
    def plain(text):
        return html.unescape(re.sub(r"<[^>]*>", "", text)).replace("Preferences → Advanced", "Settings → Advanced")
    data["commands"] = [dict(group=section.group, section=section.title,
                             phrase=" / ".join(command.said),
                             detail=plain(command.result),
                             note=plain(" ".join(x for x in (section.labs, section.note, command.note) if x)))
                        for section in commands_reference.SECTIONS for command in section.commands]
    data["system_rows"] = [dict(label="Hotkey helper", value=secure_input.running_version() or "Not running"),
                           dict(label="Typing setup", value="Installed" if secure_input.is_installed() else "Setup required")]
    try:
        status = _service().GetStatus(timeout=1.5)
        data.update(connected=True, running=bool(status.get("service_running")),
                    recording=bool(status.get("recording")),
                    engine=str(status.get("engine", "")))
    except Exception:
        data["error"] = "Dictation service is not available. Open Falco from your apps."
    return data


def execute(request):
    action = request.get("action", "snapshot")
    if action == "snapshot":
        return snapshot()
    if action == "refiner_offer":
        from . import refiner_offer, ui_jobs
        accept = request.get("accept")
        if not isinstance(accept, bool):
            raise ValueError("Choose Download or Not now.")
        if not accept:
            return refiner_offer.dismiss()
        if not refiner_offer.eligible(config.load_config()):
            raise ValueError("Your refiner setup changed. Check Settings → Refiner.")
        return ui_jobs.start("enable_refiner_acceleration")
    if action in ("start_service", "stop_service", "restart_service"):
        service = _service()
        if action == "start_service":
            service.StartService(timeout=2)
        elif action == "stop_service":
            service.StopService(timeout=2)
        else:
            service.RestartService(timeout=2)
        return {"ok": True}
    if action in ("save_settings", "download_models", "check_updates", "install_update",
                  "backup", "restore", "microphone_test", "hotkey_test", "setup_keyboard"):
        from . import ui_jobs, ui_settings
        if action == "save_settings":
            ui_settings.checked_changes(config.load_config(), request.get("changes"))
        return ui_jobs.start(action, {key: value for key, value in request.items() if key != "action"})
    if action == "cancel_job":
        from . import ui_jobs
        return ui_jobs.cancel()
    if action == "save_word":
        from . import vocabulary
        word, phrases, old = request.get("word"), request.get("phrases", []), request.get("old")
        if (not isinstance(word, str) or not isinstance(phrases, list)
                or not all(isinstance(x, str) for x in phrases)
                or old is not None and not isinstance(old, str)):
            raise ValueError("Enter a word and its alternate pronunciations.")
        vocabulary.save_word(word, phrases, old=old)
        return {"ok": True, "message": "Word saved."}
    if action == "remove_word":
        from . import vocabulary
        if not isinstance(request.get("word"), str):
            raise ValueError("Choose the word to remove.")
        vocabulary.remove_word(request["word"])
        return {"ok": True, "message": "Word removed."}
    if action in ("save_snippet", "remove_snippet"):
        from . import vocabulary
        commands = config.load_custom_commands()
        if config.custom_commands_unreadable():
            raise ValueError("Your snippets could not be read. Nothing was changed.")
        phrase, text = request.get("phrase"), request.get("text", "")
        if not isinstance(phrase, str) or not phrase.strip() or not isinstance(text, str):
            raise ValueError("Enter a trigger phrase and replacement text.")
        phrase = " ".join(phrase.split()).lower()
        if action == "save_snippet":
            old = request.get("old")
            if old is not None and not isinstance(old, str):
                raise ValueError("Choose the snippet to edit.")
            if phrase in commands and old != phrase:
                raise ValueError("This phrase is already in use. Edit its existing word or snippet first.")
            if vocabulary.is_risky(phrase):
                raise ValueError("Choose a more distinctive trigger than an everyday word.")
            if not text.strip():
                raise ValueError("Enter the text the snippet should type.")
            if old and old != phrase:
                commands.pop(old, None)
            commands[phrase] = text
        else:
            commands.pop(phrase, None)
        config.save_custom_commands(commands)
        return {"ok": True, "message": "Snippet saved." if action == "save_snippet" else "Snippet removed."}
    if action in ("clear_history", "clear_learned", "reset_stats", "clear_log"):
        if request.get("confirmed") is not True:
            raise ValueError("Confirm this action first.")
        if action == "clear_history":
            history.clear()
        elif action == "clear_learned":
            from . import learned_words
            learned_words.clear()
        elif action == "clear_log":
            from .logger import clear_log
            if not clear_log():
                raise RuntimeError("The log could not be cleared. Check file permissions and retry.")
        else:
            from . import stats
            stats.reset()
        return {"ok": True, "message": "Cleared."}
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
