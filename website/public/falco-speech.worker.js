/**
 * Browser worker for the Falco demo's on-device speech model.
 *
 * Adapted from the Cactus Compute browser sandbox worker:
 * https://github.com/cactus-compute/cactus (Apache-2.0)
 * Model: https://huggingface.co/Cactus-Compute/whistle (Apache-2.0)
 *
 * The model and WASM runtime are fetched from pinned Hugging Face revisions,
 * then kept in this tab. Audio is transcribed locally and never uploaded.
 */
"use strict";
(() => {
  const ENGINE_BASE =
    "https://huggingface.co/Cactus-Compute/cactus/resolve/1a028f5a3972b67dd8d8752f882113d475e7ec4c/releases/4.0.0/wasm";
  const MODEL_BASE =
    "https://huggingface.co/Cactus-Compute/whistle/resolve/741118687e1f008f06d1351a402a731274789790";

  const MODEL_URL = `${MODEL_BASE}/whistle.cact`;
  const OUTPUT_CAPACITY = 1 << 18;
  const scope = globalThis;

  const post = (message) => scope.postMessage(message);

  function artifactProvenance(modelUrl) {
    const modelRevision = modelUrl.split("/resolve/")[1]?.split("/")[0] ?? "unknown";
    const filename = modelUrl.split("/").at(-1) ?? "unknown";
    return {
      modelVersion: `${filename}@${modelRevision}`,
      modelRevision,
      modelSource: "huggingface",
      modelUrl,
      runtimeVersion: ENGINE_BASE.split("/releases/")[1]?.split("/")[0] ?? "unknown",
      runtimeUrl: ENGINE_BASE,
    };
  }

  async function download(url, checksum, progress) {
    const response = await fetch(url);
    if (!response.ok) throw new Error(`Download failed (${String(response.status)})`);
    let bytes;
    if (response.body && progress) {
      const reader = response.body.getReader();
      const chunks = [];
      const total = Number(response.headers.get("Content-Length")) || 0;
      let received = 0;
      for (;;) {
        const part = await reader.read();
        if (part.done) break;
        chunks.push(part.value);
        received += part.value.length;
        progress(received, total);
      }
      bytes = new Uint8Array(received);
      let offset = 0;
      for (const chunk of chunks) {
        bytes.set(chunk, offset);
        offset += chunk.length;
      }
    } else {
      bytes = new Uint8Array(await response.arrayBuffer());
    }
    if (checksum) {
      const digest = await crypto.subtle.digest("SHA-256", bytes);
      const actual = Array.from(new Uint8Array(digest), (byte) =>
        byte.toString(16).padStart(2, "0"),
      ).join("");
      if (actual !== checksum) throw new Error("Runtime checksum mismatch");
    }
    return bytes;
  }

  async function loadRuntime() {
    post({ type: "status", stage: "runtime" });
    const [source, wasm] = await Promise.all([
      download(
        `${ENGINE_BASE}/cactus.js`,
        "bb61bcf0c48712bfb9cd0ade8f0748889dfde9944ac308220f42afbc605f82bc",
      ),
      download(
        `${ENGINE_BASE}/cactus.wasm`,
        "4198b30795ded7739fe6c9e80bf26d5a844767c081574d40c8dc0487cde8b4b6",
      ),
    ]);
    const url = URL.createObjectURL(new Blob([source], { type: "text/javascript" }));
    try {
      scope.importScripts(url);
    } finally {
      URL.revokeObjectURL(url);
    }
    return scope.createCactus({ wasmBinary: wasm });
  }

  async function loadModel(engine, url, progress) {
    const bytes = await download(url, undefined, progress);
    const pointer = engine._malloc(bytes.length);
    if (!pointer) throw new Error("The model exceeds available browser memory");
    engine.HEAPU8.set(bytes, pointer);
    if (engine._cactus_load(pointer, BigInt(bytes.length)) < 0) {
      engine._free(pointer);
      throw new Error("The model could not be loaded");
    }
  }

  function allocate(engine, text) {
    if (!text) return 0;
    const bytes = new TextEncoder().encode(text);
    const pointer = engine._malloc(bytes.length + 1);
    if (!pointer) throw new Error("The speech model exceeds available browser memory");
    engine.HEAPU8.set(bytes, pointer);
    engine.HEAPU8[pointer + bytes.length] = 0;
    return pointer;
  }

  function withInput(engine, data, call) {
    const pcm = engine._malloc(data.audio.byteLength);
    if (!pcm) throw new Error("The recording exceeds available browser memory");
    let language = 0;
    let keywords = 0;
    try {
      language = allocate(engine, data.language);
      keywords = allocate(engine, data.keywords);
      engine.HEAPU8.set(
        new Uint8Array(data.audio.buffer, data.audio.byteOffset, data.audio.byteLength),
        pcm,
      );
      if (call(pcm, language, keywords) < 0) throw new Error("Transcription failed");
    } finally {
      engine._free(pcm);
      if (language) engine._free(language);
      if (keywords) engine._free(keywords);
    }
  }

  async function load() {
    const engine = await loadRuntime();
    let lastPercent = -1;
    await loadModel(engine, MODEL_URL, (received, total) => {
      const percent = total ? Math.floor((received / total) * 100) : -1;
      if (percent !== lastPercent) {
        lastPercent = percent;
        post({ type: "status", stage: "model", received, total });
      }
    });
    const output = engine._malloc(OUTPUT_CAPACITY);
    if (!output) throw new Error("The speech model exceeds available browser memory");
    post({ type: "ready" });
    return { engine, output };
  }

  let loading;
  const ready = () =>
    (loading ??= load().catch((error) => {
      loading = undefined;
      throw error;
    }));

  let streaming = 0;

  function step(engine, output, data) {
    if (data.id !== streaming) {
      engine._cactus_stream_transcribe_stop(output, OUTPUT_CAPACITY);
      streaming = data.id;
    }
    let piece = { text: "", pending: "", language: "", received: 0, pass_ms: 0 };
    if (data.audio.length) {
      withInput(engine, data, (pcm, language, keywords) =>
        engine._cactus_stream_transcribe_process(
          pcm,
          data.audio.length,
          language,
          keywords,
          output,
          OUTPUT_CAPACITY,
        ),
      );
      piece = JSON.parse(engine.UTF8ToString(output));
    }
    if (!data.end) return piece;
    streaming = 0;
    if (engine._cactus_stream_transcribe_stop(output, OUTPUT_CAPACITY) < 0) {
      throw new Error("Transcription failed");
    }
    const tail = JSON.parse(engine.UTF8ToString(output));
    return { ...tail, text: [piece.text, tail.text].filter(Boolean).join(" "), pass_ms: piece.pass_ms };
  }

  async function handle({ data }) {
    try {
      const { engine, output } = await ready();
      if (data.type === "load") return;
      const started = performance.now();
      const provenance = artifactProvenance(MODEL_URL);
      if (data.type === "stream") {
        const piece = step(engine, output, data);
        post({
          type: "step",
          id: data.id,
          step: { ...piece, text: piece.text.trim() },
          end: data.end,
          milliseconds: performance.now() - started,
          provenance,
        });
        return;
      }
      if (data.type !== "transcribe") return;
      withInput(engine, data, (pcm, language, keywords) =>
        engine._cactus_transcribe(pcm, data.audio.length, language, keywords, 0, output, OUTPUT_CAPACITY),
      );
      const transcript = JSON.parse(engine.UTF8ToString(output));
      post({
        type: "transcript",
        id: data.id,
        transcript: { ...transcript, text: transcript.text.trim() },
        milliseconds: performance.now() - started,
        provenance,
      });
    } catch (error) {
      post({
        type: "error",
        ...(data.type === "load" ? {} : { id: data.id }),
        message: error instanceof Error ? error.message : "Transcription failed",
      });
    }
  }

  scope.onmessage = (event) => void handle(event);
})();
