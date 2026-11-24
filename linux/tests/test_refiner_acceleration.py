from threading import Event, Lock
from types import SimpleNamespace
from unittest.mock import Mock

import pytest

from localdictation import ai_download, ai_server
from localdictation.config import Settings, needs_service_restart
from localdictation.hub_pins import SHA256, revision


def test_drafter_download_is_pinned_checked_and_separate(monkeypatch):
    download = Mock()
    monkeypatch.setattr('localdictation.model_helper.make_model_download_func', download)
    ai_download.make_drafter_download_func()
    download.assert_called_once_with('ai-drafter', repo_id=ai_download.MODEL_REPO,
                                     only_files=(ai_download.DRAFTER_FILE,))
    assert revision(ai_download.MODEL_REPO) == 'b20b28075046af94056ab5d5bff89a7abc0f6f50'
    assert SHA256[(ai_download.MODEL_REPO, ai_download.DRAFTER_FILE)] == (
        '56eccf7c9cb760231aee8bd6744e2144b4219987222fef770fe3970d143f5fd7')


def test_other_models_never_load_the_phonon_drafter(monkeypatch):
    cached = Mock()
    monkeypatch.setattr('localdictation.download_utils.cached_hub_file', cached)
    assert ai_download.drafter_path('gemma-3-1b') is None
    assert ai_download.drafter_path('llama-3.2-1b') is None
    cached.assert_not_called()


def test_acceleration_is_opt_in_and_changes_restart_the_engine():
    assert Settings().refiner_acceleration is False
    assert needs_service_restart({'refiner_acceleration'})


def test_failed_drafter_restarts_once_with_ordinary_decoding(monkeypatch):
    engine = ai_server.AIServer.__new__(ai_server.AIServer)
    proc = Mock()
    engine._proc = proc
    engine._lock = Lock()
    engine._ready = Event()
    engine._stopped = False
    engine._using_drafter = True
    engine._draft_disabled = False
    engine.start = Mock()
    stop = Mock()
    monkeypatch.setattr(ai_server.engine_process, 'stop', stop)
    assert engine._fallback_from_drafter(proc)
    assert engine._draft_disabled
    assert not engine._using_drafter
    engine.start.assert_called_once()
    stop.assert_called_once_with(proc)
    assert not engine._fallback_from_drafter(proc)


@pytest.mark.parametrize(('enabled', 'path'), [(True, '/draft.gguf'), (False, '/draft.gguf'),
                                             (True, None)])
def test_launch_uses_the_drafter_only_when_enabled_and_available(monkeypatch, enabled, path):
    cfg = SimpleNamespace(refiner_model='phonon', refiner_acceleration=enabled)
    monkeypatch.setattr('localdictation.config.load_config', lambda: cfg)
    monkeypatch.setattr(ai_download, 'is_installed', lambda _model: True)
    monkeypatch.setattr(ai_download, 'model_path', lambda _model: '/target.gguf')
    monkeypatch.setattr(ai_download, 'drafter_path', lambda _model: path)
    monkeypatch.setattr(ai_server, 'kill_orphaned_engines', lambda: None)
    monkeypatch.setattr(ai_server.threading, 'Thread', Mock())
    monkeypatch.setattr(ai_server.engine_process, 'OutputTail', Mock())
    engine = ai_server.AIServer([])
    engine._launcher = SimpleNamespace(popen=Mock(return_value=Mock()))
    engine.start()
    command = engine._launcher.popen.call_args.args[0]
    assert command[command.index('-m') + 1] == '/target.gguf'
    if not (enabled and path):
        assert '-md' not in command
        assert '--spec-type' not in command
        return
    assert command[command.index('-md') + 1] == '/draft.gguf'
    assert command[command.index('--spec-type') + 1] == 'draft-dflash'
    assert command[command.index('--spec-draft-n-max') + 1] == '7'


@pytest.mark.parametrize('accepted', [True, False])
def test_download_switch_enables_acceleration_only_after_success(monkeypatch, accepted):
    from localdictation import prefs_refiner
    prefs = SimpleNamespace(config={}, window=None, update_config=Mock(),
                            _untick_ai_feature=Mock())
    monkeypatch.setattr(ai_download, 'drafter_path', lambda _model: None)
    factory = Mock(return_value=Mock())
    monkeypatch.setattr(ai_download, 'make_drafter_download_func', factory)
    question = Mock(return_value=prefs_refiner.Gtk.ResponseType.OK)
    download = Mock(return_value=accepted)
    monkeypatch.setattr(prefs_refiner, 'show_message', question)
    monkeypatch.setattr(prefs_refiner, 'run_downloads', download)
    check = prefs_refiner.acceleration_option(prefs)
    download.assert_not_called()
    check.set_active(True)
    factory.assert_called_once()
    if accepted:
        prefs.update_config.assert_called_once_with('refiner_acceleration', True)
    else:
        prefs.update_config.assert_not_called()
        prefs._untick_ai_feature.assert_called_once()


def test_declining_the_drafter_download_leaves_acceleration_off(monkeypatch):
    from localdictation import prefs_refiner
    prefs = SimpleNamespace(config={}, window=None, update_config=Mock(),
                            _untick_ai_feature=Mock())
    monkeypatch.setattr(ai_download, 'drafter_path', lambda _model: None)
    monkeypatch.setattr(prefs_refiner, 'show_message', Mock(
        return_value=prefs_refiner.Gtk.ResponseType.CANCEL))
    download = Mock()
    monkeypatch.setattr(prefs_refiner, 'run_downloads', download)
    check = prefs_refiner.acceleration_option(prefs)
    check.set_active(True)
    download.assert_not_called()
    prefs.update_config.assert_not_called()
    prefs._untick_ai_feature.assert_called_once()
