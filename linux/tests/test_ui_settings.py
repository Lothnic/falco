from unittest.mock import Mock

import pytest

from localdictation import config, ui_bridge, ui_operations, ui_settings
from localdictation.ui_jobs import Cancelled


def test_every_setting_has_a_deliberate_ui_or_service_owner():
    assert ui_settings.assert_coverage() == set()
    keys = [row[1] for row in ui_settings.CATALOG]
    assert len(keys) == len(set(keys))


@pytest.mark.parametrize('changes', [
    {'model': 'not-a-model'}, {'auto_space': 'false'}, {'auto_space': 0},
    {'last_update_check': 'tomorrow'}, {'key_delay': True}, {'key_delay': 0},
    {'typing_wpm': 1}, {'indicator_sensitivity': float('nan')},
    {'device': 'cuda', 'model': 'parakeet-v3'},
    {'chunked_dictation': True, 'auto_stop_silence': True, 'chunk_pause_seconds': 3.0, 'auto_stop_seconds': 1.0},
])
def test_invalid_settings_never_start_a_job(monkeypatch, changes):
    monkeypatch.setattr(config, 'load_config', config.Settings)
    launch = Mock()
    monkeypatch.setattr('localdictation.ui_jobs.start', launch)
    with pytest.raises((ValueError, config.ConfigError)):
        ui_bridge.execute({'action':'save_settings', 'changes':changes})
    launch.assert_not_called()


def test_language_choice_updates_the_service_fields_together():
    manual = ui_settings.checked_changes(config.Settings(), {'language':'hi', 'model':'small'})
    assert manual.language == 'hi' and manual.language_mode == 'manual'
    auto = ui_settings.checked_changes(manual, {'language':''})
    assert not auto.language and auto.language_mode == 'auto'


def test_failed_download_does_not_save_settings(monkeypatch):
    monkeypatch.setattr(config, 'load_config', config.Settings)
    save = Mock()
    monkeypatch.setattr(config, 'save_config', save)
    monkeypatch.setattr(ui_operations, 'download_models', Mock(side_effect=RuntimeError('offline')))
    with pytest.raises(RuntimeError, match='offline'):
        ui_operations.save_settings({'model':'small'}, Mock(), Mock(is_set=lambda:False))
    save.assert_not_called()


def test_cancelled_download_does_not_save_settings(monkeypatch):
    monkeypatch.setattr(config, 'load_config', config.Settings)
    monkeypatch.setattr(ui_operations, 'download_models', Mock())
    save = Mock()
    monkeypatch.setattr(config, 'save_config', save)
    with pytest.raises(Cancelled):
        ui_operations.save_settings({'auto_space':False}, Mock(), Mock(is_set=lambda:True))
    save.assert_not_called()


def test_save_preserves_changes_made_elsewhere_during_a_download(monkeypatch):
    states = [config.Settings(), config.Settings(smart_quotes=False)]
    monkeypatch.setattr(config, 'load_config', lambda: states.pop(0))
    monkeypatch.setattr(ui_operations, 'download_models', Mock())
    save = Mock()
    monkeypatch.setattr(config, 'save_config', save)
    ui_operations.save_settings({'auto_space':False}, Mock(), Mock(is_set=lambda:False))
    saved = save.call_args.args[0]
    assert saved.auto_space is False and saved.smart_quotes is False


def test_editor_uses_the_existing_pronunciation_validation(monkeypatch):
    save = Mock()
    monkeypatch.setattr('localdictation.vocabulary.save_word', save)
    ui_bridge.execute({'action':'save_word','word':'Phonon','phrases':['phone on'],'old':'Fonon'})
    save.assert_called_once_with('Phonon',['phone on'],old='Fonon')


def test_clear_actions_require_confirmation(monkeypatch):
    clear = Mock()
    monkeypatch.setattr(ui_bridge.history, 'clear', clear)
    with pytest.raises(ValueError, match='Confirm'):
        ui_bridge.execute({'action':'clear_history'})
    clear.assert_not_called()
    ui_bridge.execute({'action':'clear_history', 'confirmed':True})
    clear.assert_called_once()


def test_snippet_cannot_silently_replace_an_existing_pronunciation(monkeypatch):
    monkeypatch.setattr(config,'load_custom_commands',lambda:{'phone on':'Phonon'})
    monkeypatch.setattr(config,'custom_commands_unreadable',lambda:False)
    save = Mock()
    monkeypatch.setattr(config,'save_custom_commands',save)
    with pytest.raises(ValueError,match='already in use'):
        ui_bridge.execute({'action':'save_snippet','phrase':'phone on','text':'something else'})
    save.assert_not_called()


def test_rune_launch_is_versioned_and_never_opens_gtk(monkeypatch, tmp_path):
    from localdictation import __version__, ui_launcher
    base = tmp_path/'release'
    (base/'bin').mkdir(parents=True)
    executable = base/'bin/phonon-window'
    executable.write_text('test')
    executable.chmod(0o755)
    (base/'bin/VERSION').write_text(__version__)
    monkeypatch.setattr(ui_launcher.sys,'prefix',str(base/'.venv'))
    monkeypatch.delenv('PHONON_UI_BINARY',raising=False)
    monkeypatch.delenv('FALCO_LEGACY_UI',raising=False)
    launch = Mock()
    monkeypatch.setattr(ui_launcher.subprocess,'Popen',launch)
    ui_launcher.open_dashboard('settings','refiner')
    command = launch.call_args.args[0]
    assert command == [str(executable),'--page','settings','--section','refiner']
    assert 'localdictation.prefs' not in command
