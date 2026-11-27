"""Command Mode: the shortcut, the settings, and the draft it types."""
import json
from contextlib import nullcontext
from pathlib import Path
from types import SimpleNamespace

import pytest
from evdev import ecodes

from localdictation import (ai_cleanup, commands_reference, config, help_text, history,
                            hotkey_claims, hotkey_keys, hotkeys, pipeline, recording_state,
                            ui_settings, voice_actions, voice_edit)
from localdictation.rune_indicator import RuneIndicator


def test_command_mode_is_off_by_default():
    cfg = config.Settings()
    assert cfg.command_mode is False
    assert cfg.command_hotkey == "Ctrl+Alt+C"
    assert "command_mode" in config.LIVE_APPLIED_KEYS
    assert "command_hotkey" in config.LIVE_APPLIED_KEYS


def test_settings_catalog_exposes_command_mode():
    keys = {row[1] for row in ui_settings.CATALOG}
    assert {"command_mode", "command_hotkey"} <= keys
    assert ui_settings.assert_coverage() == set()


def test_command_settings_validate():
    candidate = ui_settings.checked_changes(
        config.Settings(), {"command_mode": True, "command_hotkey": "Ctrl+Alt+X"})
    assert candidate.command_mode is True
    assert candidate.command_hotkey == "Ctrl+Alt+X"
    with pytest.raises(ValueError, match="shortcut"):
        ui_settings.checked_changes(config.Settings(), {"command_hotkey": "C"})
    with pytest.raises(ValueError, match="different shortcut"):
        ui_settings.checked_changes(
            config.Settings(), {"voice_commands_hotkey": "Ctrl+Alt+C",
                                "command_hotkey": "Ctrl+Alt+C", "command_mode": True})


def test_command_hotkey_is_watched_only_when_enabled():
    off = hotkey_keys.Hotkeys.from_settings(config.Settings())
    on = hotkey_keys.Hotkeys.from_settings(config.Settings(command_mode=True))
    assert off.command_combo is None
    assert on.command_combo is not None
    assert on.command_combo[1] in on.watched()


def test_command_shortcut_is_claimed_from_the_desktop():
    on = config.Settings(command_mode=True)
    roles = {role for role, _what, _key in hotkey_claims.keys_to_claim(on)}
    assert "command" in roles
    off = {role for role, _what, _key in hotkey_claims.keys_to_claim(config.Settings())}
    assert "command" not in off


def test_command_combo_starts_and_stops_a_command(monkeypatch):
    combo = hotkey_keys.parse_hotkey_combo("Ctrl+Alt+C")
    event = SimpleNamespace(value=1, code=combo[1])
    held = {ecodes.KEY_LEFTCTRL, ecodes.KEY_LEFTALT}
    cfg = config.Settings(command_mode=True)
    monkeypatch.setattr(hotkeys.live, "command_mode", True)
    grabbed, released, started, stopped = [], [], {}, []
    monkeypatch.setattr(hotkeys.keyboard_grab, "grab_keyboards_hiding",
                        lambda devices, keys: grabbed.append(keys))
    monkeypatch.setattr(hotkeys.keyboard_grab, "release_all", lambda: released.append(True))
    monkeypatch.setattr(hotkeys.recording, "start_recording",
                        lambda *a, **kw: started.update(kw) or recording_state.Recording(
                            command_mode=True))
    monkeypatch.setattr(hotkeys, "_stop_recording", lambda cfg: stopped.append(cfg))

    monkeypatch.setattr(hotkeys.rs.state, "is_recording", False)
    assert hotkeys._on_command_combo(event, combo, held, ["keyboard"], cfg, 0) is True
    assert started["command_mode"] is True
    assert grabbed

    monkeypatch.setattr(hotkeys.rs.state, "is_recording", True)
    monkeypatch.setattr(hotkeys.rs.state, "current",
                        recording_state.Recording(command_mode=True))
    assert hotkeys._on_command_combo(event, combo, held, ["keyboard"], cfg, 0) is True
    assert released and stopped == [cfg]


def test_command_combo_is_ignored_during_dictation(monkeypatch):
    combo = hotkey_keys.parse_hotkey_combo("Ctrl+Alt+C")
    event = SimpleNamespace(value=1, code=combo[1])
    held = {ecodes.KEY_LEFTCTRL, ecodes.KEY_LEFTALT}
    monkeypatch.setattr(hotkeys.live, "command_mode", True)
    monkeypatch.setattr(hotkeys.rs.state, "is_recording", True)
    monkeypatch.setattr(hotkeys.rs.state, "current", recording_state.Recording())
    stopped = []
    monkeypatch.setattr(hotkeys, "_stop_recording", lambda cfg: stopped.append(cfg))
    assert hotkeys._on_command_combo(event, combo, held, ["keyboard"],
                                     config.Settings(command_mode=True), 0) is True
    assert stopped == []


def test_rune_indicator_labels_a_command_recording():
    indicator = object.__new__(RuneIndicator)
    sent = []
    indicator._send = sent.append
    indicator.set_command()
    assert sent == ["command"]


def test_rune_fixture_has_command_mode():
    fixture = json.loads(
        (Path(__file__).parent.parent / "rune-overlay" / "fixtures" / "settings.json")
        .read_text(encoding="utf-8"))
    rows = {row["key"]: row for row in fixture}
    assert rows["command_mode"]["value"] == "false"
    assert rows["command_hotkey"]["value"] == "Ctrl+Alt+C"


def test_help_and_reference_mention_command_mode():
    assert "Command Mode" in dict(help_text.tabs())["Writing"]
    titles = [section.title for section in commands_reference.SECTIONS]
    assert "Command Mode" in titles


def test_ai_draft_builds_and_cleans_its_answer():
    engine = object.__new__(ai_cleanup.CorrectionEngine)
    seen = {}

    def ask(messages, max_tokens, timeout, what, on_preview=None):
        seen.update(messages=messages, max_tokens=max_tokens, timeout=timeout, what=what)
        return "```\nHi, I will be there.\n```"

    engine.is_ready = lambda: True
    engine.ask = ask
    assert engine.draft("write a reply saying I will be there") == "Hi, I will be there."
    assert seen["messages"][-1]["content"] == (
        "INSTRUCTION: write a reply saying I will be there")
    assert seen["what"] == "command draft"
    assert seen["max_tokens"] == 1200


def test_ai_draft_rejects_an_empty_answer():
    engine = object.__new__(ai_cleanup.CorrectionEngine)
    engine.is_ready = lambda: True
    engine.ask = lambda *a, **k: "None."
    assert engine.draft("write a note") is None


def _draft_harness(monkeypatch, answer="Hello there."):
    calls = {}

    class FakeAI:
        def is_ready(self):
            return True

        def draft(self, instruction):
            calls["instruction"] = instruction
            return answer

    monkeypatch.setattr(voice_edit.live, "ai_engine", FakeAI())
    monkeypatch.setattr(voice_edit.keyboard_output, "until_cancelled",
                        lambda message: nullcontext())
    monkeypatch.setattr(voice_edit.voice_commands, "navigate", lambda *a: None)
    monkeypatch.setattr(voice_actions, "run", lambda *a: None)
    monkeypatch.setattr(voice_edit.notices, "refuse_password_field", lambda beeps: False)
    monkeypatch.setattr(voice_edit, "focus_moved", lambda *a: False)
    monkeypatch.setattr(voice_edit, "_command_selection_matches", lambda *a: True)
    monkeypatch.setattr(history, "add_entry",
                        lambda text: calls.setdefault("history", []).append(text))

    def type_rewrite(result, injection_mode, message, beeps_on, into):
        calls.update(result=result, into=into)
        return "ok"

    monkeypatch.setattr(voice_edit, "_type_rewrite", type_rewrite)
    return calls


def test_draft_command_types_at_the_cursor(monkeypatch):
    calls = _draft_harness(monkeypatch)
    where = ("kitty", None)
    message = SimpleNamespace(cancelled=False)
    outcome = voice_edit._draft_command(
        lambda: "write a short note", False, "type", message, where)
    assert outcome is True
    assert calls["instruction"] == "write a short note"
    assert calls["result"] == "Hello there."
    assert calls["history"] == ["Hello there."]
    assert calls["into"] == where


def test_draft_command_runs_a_voice_action_instead(monkeypatch):
    calls = _draft_harness(monkeypatch)
    monkeypatch.setattr(voice_actions, "run", lambda *a: True)
    message = SimpleNamespace(cancelled=False)
    outcome = voice_edit._draft_command(
        lambda: "open Firefox", False, "type", message, ("kitty", None))
    assert outcome is False       # the action was done, so no draft is written
    assert "result" not in calls


def test_command_with_nothing_selected_drafts_at_the_cursor(monkeypatch):
    calls = {}
    monkeypatch.setattr(voice_edit.notices, "refuse_password_field", lambda beeps: False)
    monkeypatch.setattr(voice_edit, "_copy_selection", lambda *a: ("", None))
    monkeypatch.setattr(voice_edit, "_draft_command",
                        lambda *a: calls.update(args=a) or True)
    outcome = voice_edit._change_selection(
        lambda: "write a note", False, "type", ("kitty", None), 0,
        SimpleNamespace(cancelled=False), None, [], command=True)
    assert outcome is True
    assert calls["args"][0]() == "write a note"
    assert calls["args"][4] == ("kitty", None)


def test_draft_command_says_when_the_ai_is_missing(monkeypatch):
    monkeypatch.setattr(voice_edit, "focus_moved", lambda *a: False)
    problems = []
    monkeypatch.setattr(voice_edit.live, "ai_engine", None)
    monkeypatch.setattr(voice_edit.notices, "edit_problem",
                        lambda kind, beeps: problems.append(kind))
    outcome = voice_edit._draft_command(
        lambda: "write a note", False, "type", SimpleNamespace(cancelled=False),
        ("kitty", None))
    assert outcome is voice_edit._UNCHANGED
    assert problems == ["not_installed"]


def test_pipeline_sends_command_recordings_to_command_mode(monkeypatch):
    rec = recording_state.Recording(command_mode=True)
    monkeypatch.setattr(pipeline.rs.state, "current", rec)
    monkeypatch.setattr(pipeline.recording, "finish_capture",
                        lambda rec, beeps, notify: (["frames"], 16000))
    monkeypatch.setattr(pipeline.focused_window, "look", lambda: ("kitty", None))
    closed, finished, called = [], [], {}
    monkeypatch.setattr(pipeline.mouse_grid, "close", lambda why: closed.append(why))
    monkeypatch.setattr(pipeline, "_finish",
                        lambda message, work: finished.append(work))
    monkeypatch.setattr(pipeline.voice_edit, "transcribe_and_command",
                        lambda *args: called.update(args=args))
    pipeline.stop_recording(False, False, False, language="en", injection_mode="type")
    assert len(finished) == 1
    finished[0]()
    assert closed == ["a command"]
    assert called["args"][0] == ["frames"]
    assert called["args"][3] == "en"
    assert called["args"][4] == "type"
    assert called["args"][5] is rec.message
    assert called["args"][6] == ("kitty", None)

def test_enabling_command_mode_alone_downloads_the_ai(monkeypatch):
    from localdictation import ui_operations
    from unittest.mock import Mock
    engine, model = Mock(return_value=True), Mock(return_value=True)
    monkeypatch.setattr(ui_operations.ai_download, "make_engine_download_func", lambda: engine)
    monkeypatch.setattr(ui_operations.ai_download, "make_model_download_func", lambda name: model)
    ui_operations.download_models(config.Settings(ai_corrections=False, voice_editing=False,
                                                  command_mode=True),
                                   {"command_mode": True}, Mock(), Mock(is_set=lambda: False))
    assert engine.called and model.called


def test_draft_refuses_an_unknown_window(monkeypatch):
    calls = _draft_harness(monkeypatch)
    problems = []
    monkeypatch.setattr(voice_edit.notices, "edit_problem", lambda why, beeps: problems.append(why))
    outcome = voice_edit._draft_command(lambda: "write a note", False, "type",
                                        SimpleNamespace(cancelled=False), (None, None))
    assert outcome is voice_edit._UNCHANGED
    assert "result" not in calls
    assert problems == ["cant_check_window"]


def test_draft_does_not_type_after_focus_changes(monkeypatch):
    calls = _draft_harness(monkeypatch)
    monkeypatch.setattr(voice_edit, "focus_moved", lambda *a: True)
    monkeypatch.setattr(voice_edit.notices, "edit_problem", lambda *a: None)
    assert voice_edit._draft_command(lambda: "write a note", False, "type",
                                    SimpleNamespace(cancelled=False), ("kwrite", "original")) is voice_edit._UNCHANGED
    assert "result" not in calls


def test_draft_does_not_type_after_cancellation_or_in_password_field(monkeypatch):
    calls = _draft_harness(monkeypatch)
    message = SimpleNamespace(cancelled=True)
    assert voice_edit._draft_command(lambda: "write a note", False, "type", message,
                                    ("kwrite", "original")) is voice_edit._UNCHANGED
    assert "result" not in calls
    message.cancelled = False
    monkeypatch.setattr(voice_edit.notices, "refuse_password_field", lambda *a: True)
    assert voice_edit._draft_command(lambda: "write a note", False, "type", message,
                                    ("kwrite", "original")) is voice_edit._UNCHANGED
    assert "result" not in calls


def test_disabled_command_mode_does_not_reserve_its_shortcut():
    old = config.Settings(command_mode=False, voice_commands_hotkey="Ctrl+Alt+C")
    assert ui_settings.checked_changes(old, {"hotkey":"F8"}).hotkey == "F8"
    with pytest.raises(ValueError, match="different shortcut"):
        ui_settings.checked_changes(old, {"command_mode":True})


def test_draft_does_not_replace_a_selection_made_during_generation(monkeypatch):
    calls = _draft_harness(monkeypatch)
    monkeypatch.setattr(voice_edit, "_command_selection_matches", lambda *a: False)
    assert voice_edit._draft_command(lambda: "write a note", False, "type",
                                    SimpleNamespace(cancelled=False), ("kwrite", "original")) is voice_edit._UNCHANGED
    assert "result" not in calls


def test_command_selection_probe_restores_clipboard_and_detects_changes(monkeypatch):
    restored, problems = [], []
    monkeypatch.setattr(voice_edit, "_copy_selection", lambda *a: ("different text", lambda: restored.append(True)))
    monkeypatch.setattr(voice_edit.notices, "edit_problem", lambda why, beeps: problems.append(why))
    assert not voice_edit._command_selection_matches("original", ("kwrite", "window"), False, SimpleNamespace())
    assert restored == [True] and problems == ["selection_changed"]


def test_selected_command_does_not_overwrite_changed_text(monkeypatch):
    from unittest.mock import Mock
    monkeypatch.setattr(voice_edit, "_copy_selection", lambda *a: ("original", lambda: None))
    monkeypatch.setattr(voice_edit.notices, "refuse_password_field", lambda *a: False)
    monkeypatch.setattr(voice_edit.voice_commands, "navigate", lambda *a: None)
    monkeypatch.setattr(voice_actions, "run", lambda *a: None)
    monkeypatch.setattr(voice_edit, "_edit_with_keys", lambda *a: voice_edit._NOT_A_KEY_EDIT)
    monkeypatch.setattr(voice_edit, "_rewritten", lambda *a: "replacement")
    matches = iter((True, False))
    monkeypatch.setattr(voice_edit, "_command_selection_matches", lambda *a: next(matches))
    replace = Mock()
    monkeypatch.setattr(voice_edit, "_rewrite_over_selection", replace)
    result = voice_edit._change_selection(lambda: "make it shorter", False, "type", ("kwrite", "window"),
                                         0, SimpleNamespace(cancelled=False), None, [], command=True)
    assert result is voice_edit._UNCHANGED
    replace.assert_not_called()


def test_draft_does_not_run_an_action_after_focus_changes_during_transcription(monkeypatch):
    from unittest.mock import Mock
    _draft_harness(monkeypatch)
    monkeypatch.setattr(voice_edit, "focus_moved", lambda *a: True)
    monkeypatch.setattr(voice_edit.notices, "edit_problem", lambda *a: None)
    action = Mock(return_value=True)
    monkeypatch.setattr(voice_actions, "run", action)
    result = voice_edit._draft_command(lambda: "press enter", False, "type",
                                       SimpleNamespace(cancelled=False), ("kwrite", "original"))
    assert result is voice_edit._UNCHANGED
    action.assert_not_called()
