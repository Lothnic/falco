from dataclasses import replace
from threading import Event
from unittest.mock import Mock

import pytest

from localdictation import ai_download, config, refiner_offer, ui_bridge, ui_operations
from localdictation.ui_jobs import Cancelled


@pytest.fixture
def setup(monkeypatch):
    cfg = config.Settings(refiner_model='phonon')
    states = [cfg]
    save = Mock(side_effect=lambda value: states.__setitem__(0, value))
    monkeypatch.setattr(config, 'load_config', lambda: states[0])
    monkeypatch.setattr(config, 'save_config', save)
    monkeypatch.setattr(ai_download, 'is_installed', lambda model=None: True)
    return states, save


@pytest.mark.parametrize('changes', [
    {'refiner_acceleration': True}, {'refiner_acceleration_offered': True},
    {'ai_corrections': False, 'voice_editing': False, 'command_mode': False},
    {'refiner_model': 'gemma-3-1b'}, {'refiner_model': 'llama-3.2-1b'},
    {'refiner_model': 'auto', 'language': 'hi', 'dictation_language': 'hi'},
])
def test_offer_only_applies_to_active_unaccelerated_phonon(setup, changes):
    states, save = setup
    assert refiner_offer.eligible(states[0])
    assert not refiner_offer.eligible(replace(states[0], **changes))
    save.assert_not_called()


def test_no_offer_until_existing_refiner_files_are_ready(setup, monkeypatch):
    monkeypatch.setattr(ai_download, 'is_installed', lambda model=None: False)
    assert not refiner_offer.eligible(setup[0][0])


def test_command_mode_alone_can_receive_offer(setup):
    assert refiner_offer.eligible(replace(setup[0][0], ai_corrections=False, command_mode=True))


def test_decline_remembers_answer_without_enabling_or_downloading(setup, monkeypatch):
    download = Mock()
    monkeypatch.setattr(ai_download, 'make_drafter_download_func', download)
    ui_bridge.execute({'action': 'refiner_offer', 'accept': False})
    assert setup[0][0].refiner_acceleration_offered
    assert not setup[0][0].refiner_acceleration
    assert not refiner_offer.eligible(setup[0][0])
    download.assert_not_called()


def test_accept_starts_cancellable_job_without_prematurely_enabling(setup, monkeypatch):
    start = Mock(return_value={'ok': True, 'job_id': 'drafter'})
    monkeypatch.setattr('localdictation.ui_jobs.start', start)
    ui_bridge.execute({'action': 'refiner_offer', 'accept': True})
    start.assert_called_once_with('enable_refiner_acceleration')
    setup[1].assert_not_called()
    with pytest.raises(ValueError):
        ui_bridge.execute({'action': 'refiner_offer', 'accept': 'yes'})


def test_success_preserves_concurrent_settings_and_does_not_restart_dictation(setup, monkeypatch):
    states, save = setup
    def fetch(report, cancel):
        states[0] = replace(states[0], auto_period=False)
        return True
    monkeypatch.setattr(ai_download, 'make_drafter_download_func', lambda: fetch)
    service = Mock()
    monkeypatch.setattr(ui_bridge, '_service', service)
    result = ui_operations.perform('enable_refiner_acceleration', {}, Mock(), Event())
    assert states[0].refiner_acceleration and states[0].refiner_acceleration_offered
    assert not states[0].auto_period
    assert 'Restart dictation' in result['message']
    service.assert_not_called()
    save.assert_called_once()


@pytest.mark.parametrize('outcome', ['failed', 'cancelled', 'changed_model', 'declined_elsewhere'])
def test_failed_or_outdated_download_never_enables_acceleration(setup, monkeypatch, outcome):
    states, save = setup
    cancel = Event()
    def fetch(report, token):
        if outcome == 'failed':
            report('Not enough disk space for the drafter.', 0)
            return False
        if outcome == 'cancelled':
            cancel.set()
        else:
            states[0] = replace(states[0], **({'refiner_model': 'gemma-3-1b'} if outcome == 'changed_model'
                                            else {'refiner_acceleration_offered': True}))
        return True
    monkeypatch.setattr(ai_download, 'make_drafter_download_func', lambda: fetch)
    with pytest.raises((RuntimeError, Cancelled, ValueError)):
        refiner_offer.enable(Mock(), cancel)
    save.assert_not_called()
    assert not states[0].refiner_acceleration


def test_download_error_retains_actual_reason_instead_of_blaming_connection():
    def fetch(report, cancel):
        report('Downloading…', 20)
        report('Not enough free space: need 215 MB.', 0)
        return False
    with pytest.raises(RuntimeError, match='Not enough free space: need 215 MB.'):
        ui_operations._download(fetch, Mock(), Event())
