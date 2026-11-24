import io
import json

import pytest

from localdictation.ai_stream import PreviewCancelled, read_chat
from localdictation.ai_server import AIServer


def packet(content=None, reason=None):
    return 'data: ' + json.dumps({"choices": [{
        "delta": {"content": content}, "finish_reason": reason}]}) + '\n\n'


def stream(*parts):
    return io.BytesIO(''.join(parts).encode())


def test_stream_accumulates_unicode_and_ignores_keepalives_and_usage():
    previews = []
    answer = read_chat(stream(': ping\n\n', packet('Meet '), packet('José\nFriday.'),
                              packet(reason='stop'), 'data: {"choices": []}\n\n',
                              'data: [DONE]\n\n'), previews.append, 5)
    assert answer == 'Meet José\nFriday.'
    assert previews[0] == 'Meet '
    assert previews[-1] == answer


@pytest.mark.parametrize('ending', [
    '', packet(reason='length') + 'data: [DONE]\n\n',
    'data: [DONE]\n\n', 'data: {bad json}\n\n',
    'data: {"error": {"message": "unavailable"}}\n\n',
    packet(reason='tool_calls') + 'data: [DONE]\n\n',
    packet(reason='stop'),
])
def test_partial_or_malformed_output_is_never_a_complete_answer(ending):
    with pytest.raises(ValueError):
        read_chat(stream(packet('An unfinished rewrite'), ending), lambda _text: None, 5)


def test_a_cancelled_preview_stops_reading():
    with pytest.raises(PreviewCancelled):
        read_chat(stream(packet('Old text'), packet(reason='stop'), 'data: [DONE]\n\n'),
                  lambda _text: False, 5)


def test_overlay_failure_does_not_discard_a_valid_refinement():
    def broken(_text):
        raise RuntimeError('overlay exited')

    assert read_chat(stream(packet('Complete.'), packet(reason='stop'),
                            'data: [DONE]\n\n'), broken, 5) == 'Complete.'


def server():
    result = AIServer.__new__(AIServer)
    result._port = 1234
    result._key = 'test-key'
    return result


def test_lost_stream_clears_preview_and_retries_without_streaming(monkeypatch):
    requests = []
    responses = [stream(packet('Partial')), io.BytesIO(json.dumps({
        'choices': [{'finish_reason': 'stop', 'message': {'content': 'Complete answer'}}]
    }).encode())]

    def open_local(request, timeout):
        requests.append(json.loads(request.data))
        return responses.pop(0)

    monkeypatch.setattr('localdictation.ai_server.engine_process.open_local', open_local)
    previews = []
    assert server()._post([], 100, 5, 'test', previews.append) == 'Complete answer'
    assert requests[0]['stream'] is True
    assert 'stream' not in requests[1]
    assert requests[0]['temperature'] == 0
    assert previews == ['Partial', '']


def test_cancellation_does_not_start_another_generation(monkeypatch):
    requests = []

    def open_local(request, timeout):
        requests.append(request)
        return stream(packet('Partial'))

    monkeypatch.setattr('localdictation.ai_server.engine_process.open_local', open_local)
    assert server()._post([], 100, 5, 'test', lambda _text: False) is None
    assert len(requests) == 1
