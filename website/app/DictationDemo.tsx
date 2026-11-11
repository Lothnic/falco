"use client";

import { useEffect, useRef, useState } from "react";

type Phase =
  | "idle"
  | "preparing"
  | "listening"
  | "transcribing"
  | "inserting"
  | "inserted";

type ModelState = "loading" | "ready" | "error";

type WorkerMessage =
  | { type: "status"; stage: "runtime" | "model"; received?: number; total?: number }
  | { type: "ready" }
  | {
      type: "transcript";
      id: number;
      transcript: { text: string; language?: string };
      milliseconds?: number;
    }
  | { type: "error"; id?: number; message: string };

type Capture = {
  stop: () => Promise<void>;
  cancel: () => void;
};

const SAMPLE = "Let's move the launch to Friday.";
const SAMPLE_RATE = 16_000;
const MAX_SECONDS = 30;
const BARS = Array.from({ length: 48 }, (_, index) =>
  18 + Math.round(64 * Math.abs(Math.sin(index * 0.83 + 0.4))),
);

const LABELS: Record<Phase, string> = {
  idle: "Standby",
  preparing: "Preparing",
  listening: "Listening",
  transcribing: "Transcribing",
  inserting: "Inserting",
  inserted: "Inserted",
};

const WORKLET_SOURCE = `registerProcessor("falco-capture", class extends AudioWorkletProcessor {
  process([input]) {
    if (input && input.length) {
      const mono = new Float32Array(input[0].length);
      for (const channel of input) for (let i = 0; i < mono.length; i++) mono[i] += channel[i] / input.length;
      this.port.postMessage(mono, [mono.buffer]);
    }
    return true;
  }
});`;

function resampler(inputRate: number) {
  if (inputRate === SAMPLE_RATE) return (input: Float32Array) => input;

  const ratio = inputRate / SAMPLE_RATE;
  let position = 1;
  let previous = 1;

  return (input: Float32Array) => {
    const output = new Float32Array(
      Math.max(0, Math.ceil((input.length - position) / ratio)),
    );
    let written = 0;
    for (; position < input.length; position += ratio) {
      const index = Math.floor(position);
      const before = index === 0 ? previous : input[index - 1];
      output[written++] = before + (input[index] - before) * (position - index);
    }
    position -= input.length;
    previous = input[input.length - 1] ?? previous;
    return output.subarray(0, written);
  };
}

async function startCapture(onChunk: (chunk: Float32Array) => void): Promise<Capture> {
  if (!navigator.mediaDevices?.getUserMedia || typeof AudioWorkletNode === "undefined") {
    throw new Error("Speech capture is not supported in this browser");
  }

  const stream = await navigator.mediaDevices.getUserMedia({
    audio: { channelCount: 1, echoCancellation: true, noiseSuppression: true },
  });

  let context = new AudioContext({ sampleRate: SAMPLE_RATE });
  let source: MediaStreamAudioSourceNode;
  try {
    source = context.createMediaStreamSource(stream);
  } catch {
    await context.close();
    context = new AudioContext();
    source = context.createMediaStreamSource(stream);
  }

  try {
    const moduleURL = URL.createObjectURL(
      new Blob([WORKLET_SOURCE], { type: "text/javascript" }),
    );
    await context.audioWorklet.addModule(moduleURL);
    URL.revokeObjectURL(moduleURL);

    const node = new AudioWorkletNode(context, "falco-capture");
    const resample = resampler(context.sampleRate);
    node.port.onmessage = (event: MessageEvent<Float32Array>) => {
      onChunk(resample(event.data));
    };
    const silence = new GainNode(context, { gain: 0 });
    source.connect(node).connect(silence).connect(context.destination);
    await context.resume();
  } catch (error) {
    stream.getTracks().forEach((track) => track.stop());
    if (context.state !== "closed") await context.close();
    throw error;
  }

  const stop = async () => {
    stream.getTracks().forEach((track) => track.stop());
    if (context.state !== "closed") await context.close();
  };

  return { stop, cancel: () => void stop() };
}

export default function DictationDemo() {
  const [phase, setPhase] = useState<Phase>("idle");
  const [text, setText] = useState("");
  const [elapsed, setElapsed] = useState(0);
  const [note, setNote] = useState<string | null>(null);
  const [modelState, setModelState] = useState<ModelState>("loading");
  const [modelProgress, setModelProgress] = useState<number | null>(null);

  const busy = useRef(false);
  const pressed = useRef(false);
  const session = useRef(0);
  const request = useRef(0);
  const worker = useRef<Worker | null>(null);
  const onWorkerMessage = useRef<(data: WorkerMessage) => void>(() => {});
  const capture = useRef<Capture | null>(null);
  const chunks = useRef<Float32Array[]>([]);
  const sampleCount = useRef(0);
  const startedAt = useRef(0);
  const typeTimer = useRef<number | null>(null);
  const tickTimer = useRef<number | null>(null);
  const fallbackTimer = useRef<number | null>(null);

  function clearTimers() {
    if (typeTimer.current) window.clearInterval(typeTimer.current);
    if (tickTimer.current) window.clearInterval(tickTimer.current);
    if (fallbackTimer.current) window.clearTimeout(fallbackTimer.current);
    typeTimer.current = null;
    tickTimer.current = null;
    fallbackTimer.current = null;
  }

  function insertText(full: string, finalNote: string) {
    clearTimers();
    setNote(finalNote);
    setPhase("inserting");
    let cursor = 0;
    typeTimer.current = window.setInterval(() => {
      cursor += 1;
      setText(full.slice(0, cursor));
      if (cursor >= full.length) {
        if (typeTimer.current) window.clearInterval(typeTimer.current);
        typeTimer.current = null;
        setPhase("inserted");
        busy.current = false;
      }
    }, 26);
  }

  function fallback(reason: "microphone" | "model") {
    if (!busy.current) return;
    pressed.current = false;
    session.current += 1;
    const active = capture.current;
    capture.current = null;
    active?.cancel();
    clearTimers();
    setPhase("transcribing");
    setElapsed(0);

    const label =
      reason === "microphone"
        ? "Sample output · microphone unavailable"
        : "Sample output · on-device model unavailable";

    fallbackTimer.current = window.setTimeout(() => {
      fallbackTimer.current = null;
      if (!busy.current) return;
      insertText(SAMPLE, label);
    }, 500);
  }

  function ensureWorker() {
    if (worker.current) return worker.current;
    const instance = new Worker("/falco-speech.worker.js");
    instance.onmessage = (event: MessageEvent<WorkerMessage>) => {
      onWorkerMessage.current(event.data);
    };
    instance.onerror = () => {
      instance.terminate();
      if (worker.current === instance) worker.current = null;
      setModelState("error");
      fallback("model");
    };
    worker.current = instance;
    return instance;
  }

  function start() {
    if (busy.current) return;
    busy.current = true;
    pressed.current = true;
    clearTimers();
    setText("");
    setElapsed(0);
    setNote(
      modelState === "ready"
        ? "Waiting for microphone…"
        : "Preparing the on-device model…",
    );
    setPhase("preparing");
    chunks.current = [];
    sampleCount.current = 0;

    const sessionId = ++session.current;

    try {
      ensureWorker().postMessage({ type: "load" });
    } catch {
      setModelState("error");
      fallback("model");
      return;
    }

    startCapture((chunk) => {
      const remaining = SAMPLE_RATE * MAX_SECONDS - sampleCount.current;
      if (remaining <= 0) return;
      const slice = chunk.length > remaining ? chunk.subarray(0, remaining) : chunk;
      chunks.current.push(slice);
      sampleCount.current += slice.length;
    })
      .then((active) => {
        if (!pressed.current || sessionId !== session.current) {
          void active.cancel();
          return;
        }
        capture.current = active;
        startedAt.current = performance.now();
        setPhase("listening");
        setNote("Recording on device · release to transcribe");
        tickTimer.current = window.setInterval(() => {
          setElapsed(performance.now() - startedAt.current);
        }, 100);
      })
      .catch(() => {
        if (sessionId !== session.current) return;
        fallback("microphone");
      });
  }

  async function finish() {
    if (!pressed.current) return;
    pressed.current = false;

    const active = capture.current;
    if (!active) {
      session.current += 1;
      clearTimers();
      if (busy.current) {
        busy.current = false;
        setPhase("idle");
        setNote("Hold the key while you speak, then release.");
      }
      return;
    }

    capture.current = null;
    clearTimers();
    setPhase("transcribing");
    setNote("Transcribing in this tab…");

    try {
      await active.stop();
    } catch {
      // The captured chunks are still usable.
    }

    if (sampleCount.current < SAMPLE_RATE * 0.3) {
      busy.current = false;
      chunks.current = [];
      sampleCount.current = 0;
      setPhase("idle");
      setText("");
      setNote("Too short — hold the key while you speak.");
      return;
    }

    const audio = new Float32Array(sampleCount.current);
    let offset = 0;
    for (const chunk of chunks.current) {
      audio.set(chunk, offset);
      offset += chunk.length;
    }
    chunks.current = [];
    sampleCount.current = 0;

    const id = ++request.current;
    try {
      ensureWorker().postMessage(
        { type: "transcribe", id, audio, language: "", keywords: "" },
        [audio.buffer],
      );
    } catch {
      setModelState("error");
      fallback("model");
    }
  }

  useEffect(() => {
    onWorkerMessage.current = (data) => {
      if (data.type === "status") {
        if (data.stage === "model") {
          setModelState("loading");
          const percent =
            data.total && data.received !== undefined
              ? Math.round((data.received / data.total) * 100)
              : null;
          if (percent !== null) setModelProgress(percent);
          if (!busy.current) return;
          if (phase === "listening") return;
          setNote(
            percent === null
              ? "Downloading on-device model…"
              : `Downloading on-device model · ${percent}%`,
          );
          return;
        }
        if (busy.current) setNote("Starting the on-device engine…");
        return;
      }

      if (data.type === "ready") {
        setModelState("ready");
        setModelProgress(100);
        if (busy.current && phase === "preparing") {
          setNote("Model ready · waiting for microphone…");
        }
        return;
      }

      if (data.type === "transcript") {
        if (data.id !== request.current) return;
        const transcript = data.transcript?.text?.trim() ?? "";
        if (!transcript) {
          busy.current = false;
          setPhase("idle");
          setText("");
          setNote("No speech detected — hold and speak clearly.");
          return;
        }
        insertText(transcript, "Transcribed on device · audio never uploaded");
        return;
      }

      if (data.type === "error") {
        if (data.id === undefined) setModelState("error");
        if (data.id !== undefined && data.id !== request.current) return;
        fallback("model");
      }
    };
  });

  useEffect(() => {
    try {
      ensureWorker().postMessage({ type: "load" });
    } catch {
      // The demo reports the failure if the user tries to dictate.
    }
    // Load the model once, as soon as the page is interactive. The worker
    // keeps it in this tab for the life of the page.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  useEffect(() => {
    return () => {
      clearTimers();
      capture.current?.cancel();
      worker.current?.terminate();
      worker.current = null;
    };
    // Timers, capture and worker all live in refs for the life of the page.
  }, []);

  const defaultNote =
    modelState === "ready"
      ? "On-device model ready · audio never uploaded"
      : modelState === "error"
        ? "On-device model unavailable · demo falls back to a sample"
        : modelProgress !== null
          ? `Loading on-device model · ${modelProgress}%`
          : "Loading on-device model…";

  const seconds = (elapsed / 1000).toFixed(1).padStart(4, "0");
  const timecode = phase === "idle" ? "00:00.0" : `00:${seconds}`;
  const readout =
    text ||
    (phase === "preparing"
      ? "Preparing the on-device model…"
      : phase === "listening"
        ? "Listening…"
        : phase === "transcribing"
          ? "Transcribing in this tab…"
          : "Hold the key. Your words land in the focused app.");

  return (
    <div className="dictation-demo">
      <div className="demo-meta">
        <span>Interactive — hold to dictate</span>
        <span>
          {modelState === "ready"
            ? "On-device model · 16.9 MB"
            : modelState === "error"
              ? "On-device model unavailable"
              : modelProgress !== null
                ? `Loading model · ${modelProgress}%`
                : "Loading model…"}
        </span>
      </div>
      <div className="demo-grid">
        <button
          type="button"
          className="hold-key"
          data-live={phase === "listening"}
          aria-label="Hold to demonstrate dictation"
          onPointerDown={(event) => {
            event.currentTarget.setPointerCapture(event.pointerId);
            start();
          }}
          onPointerUp={() => void finish()}
          onPointerCancel={() => void finish()}
          onLostPointerCapture={() => void finish()}
          onKeyDown={(event) => {
            if ((event.key === " " || event.key === "Enter") && !event.repeat) {
              event.preventDefault();
              start();
            }
          }}
          onKeyUp={(event) => {
            if (event.key === " " || event.key === "Enter") {
              event.preventDefault();
              void finish();
            }
          }}
          onBlur={() => void finish()}
        >
          <span className="hold-key-top">
            <svg viewBox="0 0 24 24" aria-hidden="true">
              <rect x="9" y="3" width="6" height="11" rx="3" />
              <path d="M5.5 11.5a6.5 6.5 0 0 0 13 0M12 18v3M9 21h6" />
            </svg>
            {phase === "listening" ? "Release" : "Hold"}
          </span>
          <span className="hold-key-base">Dictate</span>
        </button>

        <div className="waveform-wrap">
          <div className="waveform" data-live={phase === "listening"} aria-hidden="true">
            {BARS.map((height, index) => (
              <i
                key={index}
                style={{
                  height: `${height}%`,
                  animationDelay: `${(index % 11) * -0.08}s`,
                }}
              />
            ))}
          </div>
          <div className="waveform-axis" aria-hidden="true">
            <span>Input</span>
            <span>On device</span>
            <span>Text out</span>
          </div>
        </div>

        <div className="demo-readout">
          <div className="readout-top">
            <span className="readout-status" data-phase={phase} role="status">
              <i aria-hidden="true" />
              {LABELS[phase]}
            </span>
            <span className="readout-time">{timecode}</span>
          </div>
          <p className="readout-text">
            {readout}
            <span
              className="readout-caret"
              data-visible={phase === "inserting" || phase === "inserted"}
              aria-hidden="true"
            />
          </p>
          <p className="readout-note">{note ?? defaultNote}</p>
        </div>
      </div>
    </div>
  );
}
