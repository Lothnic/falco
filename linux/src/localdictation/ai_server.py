"""The local AI's server: llama-server kept running while a feature that
uses it is on, and asked over HTTP on 127.0.0.1 with a key only this user
can read. What it's asked, and what's done with the answers, is the
features' own (ai_cleanup).
"""
import json
import os
import secrets
import subprocess
import threading
import time
import urllib.request

from . import ai_download, engine_process
from .ai_stream import PreviewCancelled, notify_preview, read_chat
from .logger import setup_logger

logger = setup_logger(__name__)

# A server that doesn't come up in time, or ends while starting, is stopped
# and tried again on a request at least this long after, a few times a
# session: a model on a slow disk loads faster the second time, from memory.
_RETRY_AFTER_S = 60
_MAX_FAILED_STARTS = 3


def _engine_processes():
    """(pid, parent pid) of every running llama-server from our engine folder."""
    return engine_process.processes_of(ai_download.server_binary())


def kill_orphaned_engines() -> int:
    """Kill engines whose TuxTalk service is gone. Returns how many."""
    return engine_process.kill_orphans(_engine_processes(), engine_process.is_talktype_process,
                                       "AI engine")


class AIServer:
    """A llama-server process and the requests sent to it.

    *warm_up* is the chat sent once before it counts as ready: the first
    request pays one-time setup (GPU shader compilation, filling the prompt
    cache) of up to several seconds, which this keeps off the user's first
    real one.
    """

    def __init__(self, warm_up):
        from .config import load_config
        cfg = load_config()
        self._model_id = ai_download.selected_model(cfg)
        self._acceleration = bool(cfg.refiner_acceleration)
        self._draft_disabled = False
        self._using_drafter = False
        self._warm_up = warm_up
        self._proc = None
        self._port = None
        self._key = None
        self._ready = threading.Event()
        self._lock = threading.Lock()
        self._launcher = engine_process.Launcher("ai-engine")
        self._stopped = False
        self._failed_starts = 0
        self._failed_at = None          # time.monotonic() of the last failed start

    def start(self, _replacing=None):
        """Start the server in the background. Returns immediately.
        *_replacing* is a server that exited: started again only if it is
        still this engine's (not stopped, nor restarted, meanwhile)."""
        with self._lock:
            if self._stopped or (_replacing is not None and self._proc is not _replacing):
                return
            self._failed_at = None
            if self._proc and self._proc.poll() is None:
                return
            if not ai_download.is_installed(self._model_id):
                logger.warning("The AI is on but its download is missing; skipping")
                return
            kill_orphaned_engines()
            self._ready.clear()
            self._port = engine_process.free_port()
            # A random key, so other users' programs can't use the engine. It
            # goes in the environment, which only this user can read: every
            # user can read a command line (/proc/<pid>/cmdline). This user's
            # own programs can read either, and are trusted anyway.
            self._key = secrets.token_hex(16)
            binary = ai_download.server_binary()
            draft = (ai_download.drafter_path(self._model_id)
                     if self._acceleration and not self._draft_disabled else None)
            self._using_drafter = draft is not None
            draft_args = (["-md", draft, "--spec-type", "draft-dflash",
                           "--spec-draft-n-max", "7", "--spec-draft-n-min", "0",
                           "-ngld", "99", "-fa", "on"] if draft else [])
            command, env = engine_process.parent_death_command(
                # 4096 tokens: room for a voice edit (ai_cleanup.MAX_EDIT_CHARS
                # of text and the rewrite); one slot, so it is all one request's.
                [binary, "-m", ai_download.model_path(self._model_id), "--host", "127.0.0.1",
                 "--port", str(self._port),
                 "-c", "4096", "-np", "1", "--jinja", "-ngl", "99", "--no-webui"] + draft_args,
                {**os.environ, "LD_LIBRARY_PATH": os.path.dirname(binary),
                 "LLAMA_API_KEY": self._key})
            proc = self._proc = self._launcher.popen(command, stdout=subprocess.DEVNULL,
                                                     stderr=subprocess.PIPE, env=env)
            output = engine_process.OutputTail(proc.stderr)
            logger.info(f"AI engine starting (pid {proc.pid})")
            if draft:
                logger.info("Phonon DFlash2 acceleration enabled")
        # The process started here, not self._proc read again: a stop() just
        # after the lock is let go would hand the waiter None.
        threading.Thread(target=self._wait_until_ready, args=(proc, output), daemon=True).start()

    def _wait_until_ready(self, proc, output, limit=90):
        """Wait for the server *proc* to answer, warm it up, then mark it
        ready, unless it was stopped (or replaced) meanwhile. *output* is
        what it printed (engine_process.OutputTail)."""
        deadline = time.time() + limit
        while time.time() < deadline:
            if self._proc is not proc:
                return                  # turned off while starting
            if proc.poll() is not None:
                self._start_failed(proc, "AI engine exited during startup"
                                   + engine_process.launch_failure(proc.returncode, output))
                return
            if not engine_process.answers(self._port, proc.pid):
                time.sleep(0.25)
                continue
            started = time.time()
            answered = self._post(self._warm_up, 200, timeout=60, what="AI warm-up")
            if answered is None and self._using_drafter:
                self._start_failed(proc, "Accelerated refiner warm-up failed")
                return
            with self._lock:
                if self._proc is not proc:
                    return              # stopped during the warm-up: no answer was expected
                self._ready.set()
            if answered is None:
                logger.warning("AI engine warm-up got no answer; the first request "
                               "may be slow")
            logger.info(f"AI engine ready (warm-up took {time.time() - started:.1f}s)")
            return
        self._start_failed(proc, f"AI engine did not become ready within {limit} s")

    def _start_failed(self, proc, why):
        """Let go of *proc*, a server that didn't come up, unless it was
        stopped or replaced meanwhile. Kept, it would hold its memory all
        session and never count as ready, and nothing would start another."""
        if self._fallback_from_drafter(proc):
            return
        with self._lock:
            if self._proc is not proc:
                return
            self._proc = None
            self._failed_starts += 1
            self._failed_at = time.monotonic()
        engine_process.stop(proc)
        if self._failed_starts < _MAX_FAILED_STARTS:
            logger.error(f"{why}; stopped it, and a request from {_RETRY_AFTER_S} s on "
                         "tries again")
        else:
            logger.error(f"{why}; not trying again until the AI is turned off and on")

    def _fallback_from_drafter(self, proc):
        """Retry once without drafting if acceleration cannot run on this device."""
        with self._lock:
            if self._stopped or self._proc is not proc or not self._using_drafter:
                return False
            self._proc = None
            self._ready.clear()
            self._draft_disabled = True
            self._using_drafter = False
        logger.warning("Accelerated refiner failed; restarting with ordinary decoding")
        engine_process.stop(proc)
        self.start()
        return True

    def stop(self):
        """Stop the server for good; a start still under way gives up."""
        with self._lock:
            proc, self._proc = self._proc, None
            self._stopped = True
            self._ready.clear()
        if engine_process.stop(proc):
            logger.info("AI engine stopped")
        self._launcher.close()

    def _restart_if_exited(self):
        """A server that died after it was ready (out of memory, a graphics
        driver reset) is started again, and so, a while later, is one that
        never came up (_start_failed); otherwise every request would fail
        until the option was turned off and on."""
        proc = self._proc
        if proc is None:
            if self._retry_due():
                logger.info("Starting the AI engine again after it failed to start")
                self.start()
            return
        if not self._ready.is_set() or proc.poll() is None:
            return
        logger.warning(f"AI engine exited (code {proc.returncode}); starting it again")
        if self._fallback_from_drafter(proc):
            return
        self._ready.clear()
        self.start(_replacing=proc)

    def _retry_due(self) -> bool:
        failed_at = self._failed_at
        return (failed_at is not None and self._failed_starts < _MAX_FAILED_STARTS
                and time.monotonic() - failed_at >= _RETRY_AFTER_S)

    def is_ready(self) -> bool:
        """True once the server has answered its warm-up and is still running."""
        self._restart_if_exited()
        return self._ready.is_set()

    def ask(self, messages, max_tokens, timeout, what, on_preview=None):
        """The answer's text to the chat *messages*, or None before the
        server is ready or on any problem. *what* names the request in the log."""
        if not self.is_ready():
            return None
        return self._post(messages, max_tokens, timeout, what, on_preview=on_preview)

    def _post(self, messages, max_tokens, timeout, what, on_preview=None):
        """Send a chat request; the answer's text, or None on any problem."""
        body = {"messages": messages, "temperature": 0, "max_tokens": max_tokens,
                "cache_prompt": True, "repeat_penalty": 1.0, "chat_template_kwargs": {"enable_thinking": False}}
        if on_preview is not None:
            body["stream"] = True
        request = urllib.request.Request(
            f"http://127.0.0.1:{self._port}/v1/chat/completions",
            data=json.dumps(body).encode(),
            headers={"Content-Type": "application/json", "Authorization": f"Bearer {self._key}"})
        try:
            with engine_process.open_local(request, timeout=timeout) as response:
                if on_preview is not None:
                    return read_chat(response, on_preview, timeout)
                choice = json.load(response)["choices"][0]
            if choice.get("finish_reason") == "length":
                # Cut off at max_tokens: half a rewrite must never replace the
                # whole selection, nor half a sentence the spoken one.
                logger.warning(f"{what}: the answer was cut off; not using it")
                return None
            return choice["message"]["content"].strip()
        except PreviewCancelled:
            return None
        except Exception as e:
            logger.warning(f"{what} request failed ({type(e).__name__})")
            if on_preview is not None and notify_preview(on_preview, "") is not False:
                # A lost stream must not turn a partial rewrite into the final
                # dictation. Retry through the original complete-response path.
                return self._post(messages, max_tokens, timeout, what)
            return None
