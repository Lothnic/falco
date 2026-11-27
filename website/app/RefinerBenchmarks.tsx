import run from "../public/benchmarks/refiner-2.5-linux.json";

function median(values: number[]) {
  const sorted = [...values].sort((a, b) => a - b);
  const mid = Math.floor(sorted.length / 2);
  return sorted.length % 2 ? sorted[mid] : (sorted[mid - 1] + sorted[mid]) / 2;
}

const rows = run.metadata.prompts.map((_, prompt) => {
  const baseline = run.baseline.filter((row) => row.prompt === prompt);
  const accelerated = run.accelerated.filter((row) => row.prompt === prompt);
  const before = median(baseline.map((row) => row.complete_ms));
  const after = median(accelerated.map((row) => row.complete_ms));
  return { tokens: baseline[0].timings.predicted_n, before, after, speedup: before / after };
});
const totalBefore = run.baseline.reduce((sum, row) => sum + row.complete_ms, 0);
const totalAfter = run.accelerated.reduce((sum, row) => sum + row.complete_ms, 0);
const source = "https://github.com/Lothnic/falco/blob/main/docs/benchmarks/README.md";

export default function RefinerBenchmarks() {
  return (
    <section className="section benchmarks" id="benchmarks" aria-labelledby="benchmark-title">
      <div className="shell">
        <div className="section-head">
          <p className="eyebrow">05 / Linux benchmarks</p>
          <h2 id="benchmark-title">More output.<br /><span className="accent">Less waiting.</span></h2>
          <p className="section-side">
            The 2.5 refiner engine, included in 2.5.1, pairs the Phonon refiner with an optional DFlash2 drafter. In this initial
            Linux test, the gains grew with generated output length. The longest measured output
            was 60 tokens; very long outputs and contexts have not been tested.
          </p>
        </div>
        <div className="benchmark-layout">
          <div className="benchmark-summary">
            <p className="benchmark-stat">{Math.round((1 - totalAfter / totalBefore) * 100)}<span>%</span></p>
            <h3>Less total refinement time</h3>
            <p>
              {(totalBefore / totalAfter).toFixed(2)}× faster across the measured requests.
              The 60-token output finished 1.87× faster; the shortest output changed little.
            </p>
            <p>
              Streamed text first arrived in about 47–51 ms, before overlay rendering.
              First-token generation was similar with and without the drafter; 2.5 can show
              the text while cleanup continues.
            </p>
            <a className="link-underline" href={source}>Method, scope and reproduction →</a>
          </div>
          <figure className="panel benchmark-chart">
            <div className="panel-meta"><span>Refiner request latency</span><span>Lower is faster</span></div>
            <div className="benchmark-legend">
              <span><i className="benchmark-key baseline" />2.4.2 decoding baseline</span>
              <span><i className="benchmark-key accelerated" />2.5 + DFlash2</span>
            </div>
            {rows.map((row) => (
              <div className="benchmark-case" key={row.tokens}>
                <div className="benchmark-case-label">
                  <span>{row.tokens} output tokens</span><span>{row.speedup.toFixed(2)}× faster</span>
                </div>
                <div className="benchmark-bar-row">
                  <div className="benchmark-bar baseline" style={{ width: `${row.before / 4}%` }} aria-hidden="true" />
                  <span><span className="sr-only">2.4.2: </span>{Math.round(row.before)} ms</span>
                </div>
                <div className="benchmark-bar-row">
                  <div className="benchmark-bar accelerated" style={{ width: `${row.after / 4}%` }} aria-hidden="true" />
                  <span><span className="sr-only">2.5 with DFlash2: </span>{Math.round(row.after)} ms</span>
                </div>
              </div>
            ))}
            <div className="benchmark-axis" aria-hidden="true"><span>0</span><span>100</span><span>200</span><span>300</span><span>400 ms</span></div>
            <figcaption>
              Median of two warmed runs per prompt. Linux / Vulkan · RTX 4060 Laptop GPU, 8 GB ·
              llama.cpp b12210 · same pinned Phonon target. Measured November 24, 2026.
              Four synthetic English prompts; outputs matched.
            </figcaption>
          </figure>
        </div>
        <p className="benchmark-scope">
          Refiner HTTP requests only. Excludes speech recognition, model loading, UI rendering and
          final text insertion. CPU-only and other GPUs have not been measured. Acceleration is
          optional and may be slower on some devices. <a href="/benchmarks/refiner-2.5-linux.json">Raw measurements ↗</a>
        </p>
        <div className="benchmark-enable">
          <h3>Enable refinement in Falco 2.6</h3>
          <p>
            Enable <strong>Accelerate Phonon refinement</strong> in Settings → Refiner for a one-time
            215 MB download. Enable <strong>Show live transcript</strong> in Settings → Appearance for streamed cleanup previews. Also enable <strong>Start typing sooner</strong>
            {" "}with CPU Parakeet to refine during speech pauses. Only completed, checked text is typed.
          </p>
        </div>
      </div>
    </section>
  );
}
