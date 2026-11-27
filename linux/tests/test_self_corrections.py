from unittest.mock import Mock

import pytest

from localdictation import ai_cleanup, dictation_text


@pytest.mark.parametrize('text', [
    'Meet me on Monday, no, Tuesday.',
    'Meet me on Monday. No, Tuesday.',
    'Meet me on Monday. No. Tuesday.',
    'Use red paint, not that, blue paint.',
    'Use red paint. Not that. Blue paint.',
    'Order two boxes, no wait, three boxes.',
])
def test_recognizes_explicit_spoken_replacements(text):
    assert ai_cleanup.has_correction(text)


@pytest.mark.parametrize('text', [
    'There is no problem with that.',
    'It is not that important.',
    'No problem, I can help.',
    'No one needs to leave.',
    'The answer is no.',
])
def test_ordinary_negations_are_not_correction_cues(text):
    assert not ai_cleanup.has_correction(text)
    engine = Mock()
    assert ai_cleanup.fix_self_corrections(text, engine) == text
    engine.correct.assert_not_called()


@pytest.mark.parametrize('cue', ['No, Tuesday.', 'Not that, Tuesday.', 'Not that.'])
def test_correction_after_a_pause_can_refer_to_previous_phrase(cue):
    assert ai_cleanup.opens_with_correction('Meet me on Monday.', cue)


@pytest.mark.parametrize(('said', 'asked', 'answer'), [
    ('Meet me on Monday, no, Tuesday.', 'Meet me on Monday, no, Tuesday.', 'Meet me on Tuesday.'),
    ('Use red paint, not that, blue paint.', 'Use red paint, not that, blue paint.', 'Use blue paint.'),
    ('Use red paint. Not that. Blue paint.', 'Use red paint, not that, Blue paint.', 'Use blue paint.'),
    ('Meet me on Monday. No. Tuesday.', 'Meet me on Monday, no, Tuesday.', 'Meet me on Tuesday.'),
])
def test_only_corrected_version_survives_including_split_sentences(said, asked, answer):
    engine = Mock()
    engine.correct.return_value = answer
    assert ai_cleanup.fix_self_corrections(said, engine) == answer
    engine.correct.assert_called_once_with(asked)


def test_unsafe_replacement_keeps_spoken_text():
    said = 'Meet me on Monday, no, Tuesday.'
    engine = Mock()
    engine.correct.return_value = 'Meet me on Friday.'
    assert ai_cleanup.fix_self_corrections(said, engine) == said


def test_a_verified_correction_can_be_shorter_than_generic_length_guard(monkeypatch):
    raw = 'Order red paint, not that, no wait, blue paint.'
    engine = Mock()
    engine.correct.return_value = 'Order blue paint.'
    monkeypatch.setattr(dictation_text.live, 'ai_engine', engine)
    assert dictation_text.refine(raw) == 'Order blue paint.'


def test_correction_cue_does_not_allow_dropping_unrelated_details(monkeypatch):
    raw = 'Call Alice about the invoice and arrange delivery on Monday, no wait, Tuesday.'
    engine = Mock()
    engine.correct.return_value = 'Tuesday.'
    monkeypatch.setattr(dictation_text.live, 'ai_engine', engine)
    assert dictation_text.refine(raw) is None


def test_collapsed_long_dictation_falls_back_without_exploring_structural_splices(monkeypatch):
    raw = ('Keep this important detail in the final document. ' * 40) + 'No wait, Tuesday.'
    engine = Mock()
    engine.correct.return_value = 'Tuesday.'
    monkeypatch.setattr(dictation_text.live, 'ai_engine', engine)
    structural_check = Mock(side_effect=AssertionError('Long dictations must use the normal length guard'))
    monkeypatch.setattr('localdictation.correction_safety.edit_is_safe', structural_check)
    assert dictation_text.refine(raw) is None
    structural_check.assert_not_called()


def test_phonon_prompt_explicitly_handles_corrections_without_erasing_negation():
    prompt = ai_cleanup._correction_messages('raw words')[0]['content']
    assert 'not that' in prompt and 'self-corrections' in prompt
    assert 'ordinary negations' in prompt
    assert prompt.endswith('Writing mode: minimal (notes and documents).')


@pytest.mark.parametrize('cue', ['Not that, blue paint.', 'No, blue paint.'])
def test_pause_correction_replaces_only_the_previous_phrase_when_typing_is_safe(monkeypatch, cue):
    from localdictation import recording_state, type_at_pause
    engine = Mock()
    engine.correct.return_value = 'Use blue paint.'
    monkeypatch.setattr(type_at_pause.live, 'ai_corrections', True)
    monkeypatch.setattr(type_at_pause.live, 'ai_engine', engine)
    monkeypatch.setattr(recording_state.state, 'last_inserted_text', 'Use red paint. ')
    message = recording_state.Message(has_words=True)
    assert type_at_pause.corrects_across_pause(cue, 'middle', message)
    erase = Mock(return_value=False)
    monkeypatch.setattr(type_at_pause, '_erase_typed', erase)
    assert type_at_pause.correct_across_pause(cue, message) == (cue, '')
    erase.assert_called_once_with('Use red paint. ')
    erase.reset_mock()
    erase.return_value = True
    assert type_at_pause.correct_across_pause(cue, message) == ('Use blue paint.', 'Use red paint. ')
    erase.assert_called_once_with('Use red paint. ')
    message.complete = False
    assert not type_at_pause.corrects_across_pause(cue, 'middle', message)


def test_verified_short_correction_is_also_used_from_prefetch(monkeypatch):
    from localdictation import refiner_prefetch
    raw = 'Order red paint, not that, no wait, blue paint.'
    engine = Mock()
    engine.correct.return_value = 'Order blue paint.'
    monkeypatch.setattr(dictation_text.live, 'ai_engine', engine)
    serial = refiner_prefetch.begin()
    thread = refiner_prefetch.offer(raw, dictation_text.refine, serial,
                                   key=dictation_text.refinement_key('minimal'))
    thread.join(timeout=5)
    assert not thread.is_alive()
    assert refiner_prefetch.take(raw, serial, key=dictation_text.refinement_key('minimal')) == 'Order blue paint.'
    assert engine.correct.call_count == 1
