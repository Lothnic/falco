"""Compare the pinned refiner with/without DFlash2, including actual SSE output.

Run from the repository root with PYTHONPATH=linux/src. Models must already
be downloaded. This launches separate temporary servers and never changes
Falco's settings or running service.
"""
import argparse
import json
import os
import secrets
import socket
import subprocess
import tempfile
import time
import urllib.request
from pathlib import Path

from localdictation.ai_cleanup import _correction_messages
from localdictation.ai_stream import read_chat

PROMPTS = (
    "um send the report on tuesday no wait thursday morning",
    "okay the build is ready and the the tests are passing",
    ("please update the readme with the installation steps and mention that everything "
    "runs locally on the computer no wait mention that dictation runs locally after "
     "the models are downloaded"),
    ("so for the next release we need to finish the streaming refiner then test the "
    "download process on a clean machine and check that the overlay still works if "
    "someone starts a second recording while the first one is finishing also make "
     "sure cancelling a recording never types an incomplete response into the editor"),
)


def benchmark(args, drafting):
    with socket.socket() as sock:
        sock.bind(('127.0.0.1', 0))
        port = sock.getsockname()[1]
    key = secrets.token_hex(16)
    command = [str(args.server), '-m', str(args.model), '--host', '127.0.0.1',
               '--port', str(port), '-c', '4096', '-np', '1', '--jinja',
               '-ngl', '99', '--no-webui']
    if drafting:
        command += ['-md', str(args.drafter), '--spec-type', 'draft-dflash',
                    '--spec-draft-n-max', str(args.draft_tokens), '--spec-draft-n-min', '0',
                    '-ngld', '99', '-fa', 'on']
    opener = urllib.request.build_opener(urllib.request.ProxyHandler({}))
    base = f'http://127.0.0.1:{port}'
    headers = {'Authorization': f'Bearer {key}', 'Content-Type': 'application/json'}

    def request(path, body=None, timeout=90):
        return opener.open(urllib.request.Request(
            base + path, data=json.dumps(body).encode() if body is not None else None,
            headers=headers), timeout=timeout)

    with tempfile.TemporaryFile(mode='w+') as log:
        proc = subprocess.Popen(command, stdout=log, stderr=log, env={
            **os.environ, 'LLAMA_API_KEY': key, 'LD_LIBRARY_PATH': str(args.server.parent)})
        try:
            deadline = time.monotonic() + 120
            while True:
                try:
                    with request('/health', timeout=1) as response:
                        if response.status == 200:
                            break
                except OSError:
                    if proc.poll() is not None or time.monotonic() > deadline:
                        log.seek(0)
                        raise RuntimeError('Refiner did not start:\n' + log.read()[-6000:]) from None
                    time.sleep(0.2)
            rows = []
            # One full warm-up round, then alternate full and streamed requests.
            for iteration in range(args.rounds + 1):
                for index, prompt in enumerate(PROMPTS):
                    body = {'messages': _correction_messages(prompt), 'temperature': 0,
                            'max_tokens': 256, 'cache_prompt': True, 'repeat_penalty': 1.0,
                            'chat_template_kwargs': {'enable_thinking': False}}
                    started = time.perf_counter()
                    with request('/v1/chat/completions', body) as response:
                        result = json.load(response)
                    elapsed = time.perf_counter() - started
                    choice = result['choices'][0]
                    if choice['finish_reason'] != 'stop':
                        raise RuntimeError('Benchmark generation was truncated')
                    answer = choice['message']['content'].strip()
                    first = []
                    stream_started = time.perf_counter()

                    def preview(text, first=first, started=stream_started):
                        if text and not first:
                            first.append(time.perf_counter() - started)

                    body['stream'] = True
                    with request('/v1/chat/completions', body) as response:
                        streamed = read_chat(response, preview, 90)
                    stream_elapsed = time.perf_counter() - stream_started
                    if streamed != answer:
                        raise RuntimeError('Streamed answer differs from the complete answer')
                    if iteration:
                        rows.append({'round': iteration, 'prompt': index, 'answer': answer,
                                     'complete_ms': round(elapsed * 1000, 2),
                                     'first_text_ms': round(first[0] * 1000, 2),
                                     'stream_ms': round(stream_elapsed * 1000, 2),
                                     'timings': result.get('timings', {})})
            return rows
        finally:
            proc.terminate()
            try:
                proc.wait(timeout=10)
            except subprocess.TimeoutExpired:
                proc.kill()
                proc.wait()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    for option in ('server', 'model', 'drafter', 'output'):
        parser.add_argument('--' + option, type=Path, required=True)
    parser.add_argument('--rounds', type=int, default=2)
    parser.add_argument('--draft-tokens', type=int, choices=range(1, 8), default=7)
    args = parser.parse_args()
    if args.rounds < 1:
        parser.error('--rounds must be positive')
    result = {'draft_tokens': args.draft_tokens,
              'baseline': benchmark(args, False), 'accelerated': benchmark(args, True)}
    result['output_parity'] = all(a['answer'] == b['answer'] for a, b in zip(
        result['baseline'], result['accelerated'], strict=True))
    args.output.write_text(json.dumps(result, indent=2) + '\n')
    print(f'Output parity: {result["output_parity"]}. Measurements: {args.output}')
    if not result['output_parity']:
        raise SystemExit(1)


if __name__ == '__main__':
    main()
