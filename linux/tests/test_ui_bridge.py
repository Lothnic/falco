"""Check that the Rune UI only performs the requested local operations."""
from types import SimpleNamespace
from unittest.mock import Mock

import pytest
from localdictation import ui_bridge


def test_snapshot_uses_service_and_reports_actual_refiner_state(monkeypatch):
    cfg = SimpleNamespace(hotkey="F8", toggle_hotkey="F9", mic="", model="parakeet-v3",
                          ai_corrections=True, auto_space=True, auto_period=False)
    monkeypatch.setattr(ui_bridge.config, "load_config", lambda: cfg)
    monkeypatch.setattr(ui_bridge.ai_download, "is_installed", lambda: False)
    monkeypatch.setattr(ui_bridge.custom_words, "load", lambda: ["Parakeet"])
    monkeypatch.setattr(ui_bridge.history, "get_entries", lambda: ["Example"])
    service = Mock()
    service.GetStatus.return_value = {"service_running": True, "recording": False, "engine": "CPU"}
    monkeypatch.setattr(ui_bridge, "_service", lambda: service)
    data = ui_bridge.snapshot()
    assert data["connected"] and data["running"]
    assert data["refiner"] and not data["refiner_installed"]
    assert data["recent"] == ["Example"] and data["words"] == ["Parakeet"]


def test_setting_changes_are_restricted_to_allowed_booleans(monkeypatch):
    cfg = SimpleNamespace(auto_space=True, auto_period=True)
    save = Mock()
    monkeypatch.setattr(ui_bridge.config, "load_config", lambda: cfg)
    monkeypatch.setattr(ui_bridge.config, "save_config", save)
    assert ui_bridge.execute({"action": "set_option", "name": "auto_period", "value": False}) == {"ok": True}
    assert cfg.auto_period is False
    with pytest.raises(ValueError):
        ui_bridge.execute({"action": "set_option", "name": "hotkey", "value": "F1"})
    assert save.call_count == 1


def test_add_word_uses_existing_validation(monkeypatch):
    from localdictation import vocabulary
    save = Mock()
    monkeypatch.setattr(vocabulary, "save_word", save)
    assert ui_bridge.execute({"action": "add_word", "word": "Parakeet"}) == {"ok": True}
    save.assert_called_once_with("Parakeet", [])
    with pytest.raises(ValueError):
        ui_bridge.execute({"action": "add_word", "word": None})
