from unittest.mock import Mock

import pytest

from localdictation import ui_jobs


@pytest.fixture
def state(monkeypatch, tmp_path):
    monkeypatch.setattr(ui_jobs,'_path',lambda:str(tmp_path/'job.json'))


def test_start_returns_job_identity_and_another_job_cannot_replace_it(state, monkeypatch):
    monkeypatch.setattr(ui_jobs.subprocess,'Popen',Mock(return_value=Mock(pid=123)))
    result = ui_jobs.start('save_settings',{'changes':{'auto_space':False}})
    assert result['job_id'] == ui_jobs._read()['id']
    with pytest.raises(ValueError,match='Another operation'):
        ui_jobs.start('download_models')
    assert ui_jobs._read()['kind'] == 'save_settings'


def test_cancel_survives_progress_updates(state):
    ui_jobs._write({'busy':True,'kind':'save_settings','payload':{},'cancelled':False,'cancellable':True})
    ui_jobs.cancel()
    ui_jobs.report('Still downloading',30)
    assert ui_jobs.Cancellation().is_set()
    assert ui_jobs._read()['progress'] == 30


def test_a_failed_worker_start_does_not_leave_controls_busy(state, monkeypatch):
    monkeypatch.setattr(ui_jobs.subprocess,'Popen',Mock(side_effect=OSError('cannot start')))
    with pytest.raises(OSError):
        ui_jobs.start('download_models')
    assert not ui_jobs._read()['busy']


def test_dead_worker_is_reported_as_interrupted(state, monkeypatch):
    ui_jobs._write({'busy':True,'pid':123})
    monkeypatch.setattr(ui_jobs.os,'kill',Mock(side_effect=ProcessLookupError))
    status = ui_jobs.status()
    assert not status['busy'] and status['failed']


def test_job_status_uses_private_fallback_without_a_login_runtime(monkeypatch, tmp_path):
    monkeypatch.setattr(ui_jobs.single_instance, 'private_session_dir', lambda: None)
    monkeypatch.setattr(ui_jobs.single_instance, 'runtime_dir', lambda: str(tmp_path))
    assert ui_jobs._path() == str(tmp_path / 'dashboard-job.json')
