"""The editable settings contract shared by the Rune UI and its service bridge.

Only fields in this catalog are writable. Internal migration flags and update
timestamps stay owned by the service. Values are validated before downloading
anything or touching the saved configuration.
"""
import math
import re
from dataclasses import asdict, fields, replace

from . import config
from .recommend import LANGUAGES

# Section, key, visible label, explanation. The dataclass supplies value types.
CATALOG = (
    ("general", "hotkey", "Hold to talk", "Hold this key while speaking."),
    ("general", "toggle_hotkey", "Toggle recording", "Press once to start and again to finish. Empty disables it."),
    ("general", "voice_commands_hotkey", "Command reference shortcut", "Opens the voice command reference."),
    ("general", "paste_last_hotkey", "Paste last dictation shortcut", "Empty disables this shortcut."),
    ("general", "command_mode", "Command Mode", "Wayland only. Speak an instruction to rewrite a selection or draft new text. Downloads the local AI if needed."),
    ("general", "command_hotkey", "Command Mode shortcut", "Press once to start and again to finish. Empty disables it."),
    ("general", "mode", "Recording mode", "Use hold-to-talk or toggle recording."),
    ("general", "launch_at_login", "Launch at login", "Start Falco when you sign in."),
    ("general", "auto_timeout_enabled", "Stop when idle", "Release the speech model after inactivity."),
    ("general", "auto_timeout_minutes", "Idle timeout (minutes)", "Must be greater than zero."),
    ("speech", "model", "Speech model", "Parakeet for supported European languages; Whisper for more languages."),
    ("speech", "device", "Processing device", "CPU works everywhere. Vulkan uses a GPU; CUDA requires NVIDIA."),
    ("speech", "language", "Dictation language", "Automatic detection or the language you speak."),
    ("speech", "auto_languages", "Limit automatic detection", "Optional comma-separated language codes, such as en,hi."),
    ("audio", "mic", "Microphone", "System default follows the input chosen by your desktop."),
    ("audio", "beeps", "Recording sounds", "Play a sound when recording starts and finishes."),
    ("audio", "notify", "Desktop notifications", "Notifications may include a transcript preview."),
    ("audio", "pause_media", "Pause other media", "Pause playing music and video while recording."),
    ("audio", "resume_media", "Resume media afterwards", "Resume only players that Falco paused."),
    ("audio", "duck_audio", "Lower other audio", "Restore the original volume after recording."),
    ("audio", "auto_stop_silence", "Stop after silence", "Finish toggle recordings when you stop speaking."),
    ("audio", "auto_stop_seconds", "Silence before stopping (seconds)", "Between 0.5 and 10 seconds."),
    ("audio", "streaming_dictation", "Start typing sooner", "Hear phrases during pauses with CPU Parakeet."),
    ("audio", "chunked_dictation", "Type at pauses", "Insert each phrase while recording. Experimental."),
    ("audio", "chunk_pause_seconds", "Pause length (seconds)", "Between 0.3 and 3 seconds; shorter than auto-stop."),
    ("audio", "chunk_context_marks", "Use phrase context", "Consider adjoining phrases when choosing punctuation."),
    ("refiner", "ai_corrections", "Refine dictation", "Clean up transcripts locally. Missing models download before saving."),
    ("refiner", "refiner_model", "Refiner model", "Automatic uses Phonon for English and Gemma for Hindi."),
    ("refiner", "refiner_mode", "Writing style", "Keep your wording while adjusting the style for its destination."),
    ("refiner", "refiner_acceleration", "Accelerate Phonon refinement", "Optional 215 MB download. Turn off if slower on your hardware."),
    ("refiner", "learn_words", "Learn corrected names", "Remember names the refiner repeatedly corrects."),
    ("refiner", "voice_editing", "Voice editing", "Shift + the dictation key rewrites selected text. Experimental."),
    ("text", "auto_space", "Space after dictation", "Leave a space ready for the next phrase."),
    ("text", "auto_period", "End with punctuation", "Add a closing period where appropriate."),
    ("text", "smart_quotes", "Smart quotes", "Use typographic quotation marks."),
    ("text", "remove_fillers", "Remove fillers and repeats", "Remove um, uh and accidental repeated words using local rules."),
    ("text", "numbers_as_digits", "Write numbers as digits", "Convert spoken numbers in supported languages."),
    ("text", "numbers_small_as_words", "Keep small numbers as words", "Keep a lone one through nine as words."),
    ("text", "swiss_spelling", "Swiss German spelling", "Use ss in place of ß."),
    ("text", "adapt_to_app", "Adapt to the focused app", "Use plain text in terminals and code editors."),
    ("text", "developer_mode", "Developer mode", "Handle spoken file names, casing and symbols as code."),
    ("text", "injection_mode", "Text insertion", "Automatic chooses typing or clipboard paste for the app."),
    ("text", "key_delay", "Typing delay (milliseconds)", "Between 1 and 50. Increase if an app drops characters."),
    ("text", "restore_clipboard", "Restore clipboard", "Put back the item copied before a dictation paste."),
    ("text", "press_enter_after", "Send automatically", "Press Enter after dictation. Use care in messaging apps."),
    ("text", "press_enter_delay", "Wait before sending (seconds)", "Between 0 and 4. Tap the dictation key to hold a send."),
    ("appearance", "recording_indicator", "Show recording overlay", "Display listening and finishing status."),
    ("appearance", "rune_live_preview", "Show live transcript", "Show provisional words and streamed cleanup in Rune."),
    ("appearance", "indicator_position", "Fallback overlay position", "Applies to the GTK fallback; Rune stays at the bottom of the screen."),
    ("appearance", "indicator_size", "Fallback overlay size", "Used when the Rune recording overlay is unavailable."),
    ("appearance", "indicator_style", "Fallback overlay style", "Used when the Rune recording overlay is unavailable."),
    ("appearance", "indicator_color_mode", "Fallback overlay color mode", "Use the desktop accent or a custom color."),
    ("appearance", "indicator_color", "Fallback overlay color", "A color in #RRGGBB format."),
    ("appearance", "indicator_sensitivity", "Overlay sensitivity", "Between 0.5 and 2. Used by the fallback meter."),
    ("appearance", "indicator_follows_window", "Fallback follows focused window", "Position the fallback overlay beside the app being dictated into."),
    ("appearance", "indicator_offset_x", "Fallback horizontal offset", "Pixels from its anchor; negative values move left."),
    ("appearance", "indicator_offset_y", "Fallback vertical offset", "Pixels from its anchor; negative values move up."),
    ("advanced", "voice_navigation", "Navigate by voice", "Select text and move the cursor. Experimental."),
    ("advanced", "open_apps", "Control apps by voice", "Open apps, switch windows and use the mouse grid. Experimental."),
    ("advanced", "log_transcripts", "Log transcript text", "Off for privacy. Enabling writes your dictated words to the local log."),
    ("stats", "usage_stats", "Keep usage statistics", "Counts and durations only; never stores dictated text."),
    ("stats", "typing_wpm", "Your typing speed (words/min)", "Used to estimate time saved; between 10 and 200."),
    ("updates", "auto_check_updates", "Check for updates automatically", "Check once a day when Falco starts."),
)

MANAGED = {"language_mode", "last_update_check", "dictation_language",
           "recommend_notice_shown", "parakeet_update_offered", "vulkan_slower"}
CHOICES = {
    "hotkey": [("", "Not configured"), *[(x, x) for x in config.HOTKEY_CHOICES]],
    "toggle_hotkey": [("", "Disabled"), *[(x, x) for x in config.HOTKEY_CHOICES]],
    "mode": [("hold", "Hold to talk"), ("toggle", "Toggle")],
    "model": [(x, x.replace("parakeet-v3", "Parakeet Ultra v3").title()) for x in sorted(config.VALID_MODELS)],
    "device": [("cpu", "CPU"), ("vulkan", "GPU · Vulkan"), ("cuda", "NVIDIA · CUDA")],
    "language": [("", "Detect automatically"), *LANGUAGES],
    "refiner_model": [("auto", "Automatic"), ("phonon", "Phonon English · 1.7B"),
                      ("gemma-3-1b", "Gemma 3 · 1B"), ("llama-3.2-1b", "Llama 3.2 · 1B")],
    "refiner_mode": list(config.REFINER_MODES.items()),
    "developer_mode": list(config.DEVELOPER_MODES.items()),
    "injection_mode": [("auto", "Automatic"), ("type", "Type with keyboard"), ("paste", "Clipboard paste")],
    "indicator_position": [(x, x.replace("-", " ").title()) for x in sorted(config.VALID_INDICATOR_POSITIONS)],
    "indicator_size": [(x, x.title()) for x in ("small", "medium", "large")],
    "indicator_style": [(x, x.title()) for x in sorted(config.VALID_INDICATOR_STYLES)],
    "indicator_color_mode": [("system", "Desktop accent"), ("custom", "Custom color")],
}


def catalog(settings):
    """Fully typed, ordered form metadata. No defaults are mistaken for live status."""
    rows = []
    from .microphones import _sound_devices
    microphones = [("", "System default"), *[(d["name"], d["name"]) for d in _sound_devices() or []
                                            if d.get("max_input_channels", 0) > 0]]
    for section, key, label, hint in CATALOG:
        value = getattr(settings, key)
        options = microphones if key == "mic" else CHOICES.get(key, [])
        if options and str(value) not in {x[0] for x in options}:
            options = [*options, (str(value), str(value))]
        rows.append(dict(section=section, key=key, label=label, hint=hint,
                         datatype="bool" if isinstance(value, bool) else "int" if isinstance(value, int) else "float" if isinstance(value, float) else "str",
                         kind="bool" if isinstance(value, bool) else "choice" if options else "text",
                         value=str(value).lower() if isinstance(value, bool) else str(value),
                         choices=[dict(value=a, label=b) for a, b in options]))
    return rows


def checked_changes(settings, changes):
    """Return a validated candidate; reject unknown keys and type coercion traps."""
    if not isinstance(changes, dict) or not changes:
        raise ValueError("No settings changes to save.")
    allowed = {row[1] for row in CATALOG}
    values = asdict(settings)
    for key, value in changes.items():
        if key not in allowed:
            raise ValueError("Unknown or read-only setting.")
        current = values[key]
        if isinstance(current, bool):
            if not isinstance(value, bool):
                raise ValueError(f"{key} must be on or off.")
        elif isinstance(current, int):
            if isinstance(value, bool) or not isinstance(value, int):
                raise ValueError(f"{key} must be a whole number.")
        elif isinstance(current, float):
            if isinstance(value, bool) or not isinstance(value, (int, float)) or not math.isfinite(value):
                raise ValueError(f"{key} must be a finite number.")
        elif not isinstance(value, str) or len(value) > 4096:
            raise ValueError(f"{key} must be text of at most 4096 characters.")
    if "indicator_color" in changes and not re.fullmatch(r"#[0-9a-fA-F]{6}", changes["indicator_color"]):
        raise ValueError("Enter a color in #RRGGBB format.")
    for key in ("hotkey", "toggle_hotkey"):
        if key in changes and changes[key] and changes[key] not in config.HOTKEY_CHOICES:
            raise ValueError("Choose a supported dictation shortcut.")
    from .hotkey_keys import parse_hotkey_combo
    for key, example in (("voice_commands_hotkey", "Ctrl+Alt+V"),
                         ("paste_last_hotkey", "Ctrl+Alt+P"),
                         ("command_hotkey", "Ctrl+Alt+C")):
        if key in changes and changes[key] and parse_hotkey_combo(changes[key]) is None:
            raise ValueError(f"Use a shortcut such as {example}, or leave it empty to disable it.")
    shortcut_keys = ("hotkey", "toggle_hotkey", "voice_commands_hotkey", "paste_last_hotkey",
                     "command_hotkey")
    if (set(shortcut_keys) | {"command_mode"}) & changes.keys():
        active = changes.get("command_mode", values["command_mode"])
        shortcuts = [changes.get(key, values[key]).replace(" ", "").upper()
                     for key in shortcut_keys if key != "command_hotkey" or active]
        configured = [key for key in shortcuts if key]
        if len(configured) != len(set(configured)):
            raise ValueError("Choose a different shortcut for each action.")
    candidate = replace(settings, **changes)
    if {"model", "device"} & changes.keys() and candidate.model == "parakeet-v3" and candidate.device == "cuda":
        raise ValueError("Parakeet uses CPU or Vulkan. Choose Vulkan for GPU dictation, or Whisper for CUDA.")
    if "language" in changes:
        candidate.language_mode = "manual" if candidate.language else "auto"
    if not 10 <= candidate.typing_wpm <= 200:
        raise ValueError("Typing speed must be between 10 and 200.")
    if candidate.chunked_dictation and candidate.auto_stop_silence and candidate.chunk_pause_seconds >= candidate.auto_stop_seconds:
        raise ValueError("The phrase pause must be shorter than the auto-stop silence.")
    config.validate_config(candidate)
    return candidate


def assert_coverage():
    """A new setting must be deliberately exposed or classified as service-owned."""
    return {f.name for f in fields(config.Settings)} - {row[1] for row in CATALOG} - MANAGED
