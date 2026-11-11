import CopyCommand from "./CopyCommand";
import DictationDemo from "./DictationDemo";
import ThemeToggle from "./ThemeToggle";

const nav = [
  { href: "#signal", label: "Signal path" },
  { href: "#capabilities", label: "Capabilities" },
  { href: "#privacy", label: "Privacy" },
  { href: "#install", label: "Install" },
];

const stats = [
  { value: "0", unit: "B", label: "Audio uploaded to a cloud service" },
  { value: "1.7", unit: "GB", label: "One-time download for speech and refiner" },
  { value: "1", unit: "KEY", label: "Hold to dictate, release to insert" },
  { value: "MIT", unit: "", label: "License for the Falco app code" },
];

const stages = [
  {
    label: "01 / Capture",
    title: "Press and speak.",
    body: "Hold your dictation key. The recording indicator appears and audio is captured from the microphone.",
  },
  {
    label: "02 / Transcribe",
    title: "Parakeet listens locally.",
    body: "Parakeet Ultra v3 turns speech into text on the CPU or through Vulkan. Whisper models add more languages and CUDA.",
  },
  {
    label: "03 / Refine",
    title: "Fillers out. Meaning kept.",
    body: "Optional local cleanup fixes self-corrections, removes false starts, and tidies capitalization. The refiner is English-only.",
  },
  {
    label: "04 / Insert",
    title: "Text at the cursor.",
    body: "Falco types into the focused app on Wayland or X11. No window switching, no copy-paste dance.",
  },
];

const capabilities = [
  {
    title: "Dictate anywhere",
    body: "Hold a configurable key to talk, or use a toggle key. The words land in whichever app has focus.",
    meta: "Wayland · X11",
  },
  {
    title: "On-device recognition",
    body: "Parakeet Ultra v3 is the default. Whisper models cover more languages and can use CUDA.",
    meta: "CPU · Vulkan · CUDA",
  },
  {
    title: "Optional cleanup",
    body: "The local Phonon refiner removes fillers and false starts. Dictation works without it, too.",
    meta: "English · ~1 GB",
  },
  {
    title: "Your vocabulary",
    body: "Custom words steer recognition. Voice commands handle punctuation, formatting, undo, and fixes.",
    meta: "Custom words",
  },
  {
    title: "Rune dashboard",
    body: "Overview, recent dictations, your words, and settings, plus a sound-responsive recording overlay.",
    meta: "Experimental · Rust",
  },
  {
    title: "Private by design",
    body: "No account, no metered minutes, no audio upload. Dictation works offline once the models are installed.",
    meta: "Offline ready",
  },
];

const processRows = [
  {
    index: "01",
    title: "Press",
    body: "Hold the dictation key. A small indicator confirms that Falco is listening.",
    bar: "Key down",
    start: "0%",
    width: "12%",
  },
  {
    index: "02",
    title: "Speak",
    body: "Talk naturally. Audio is captured and transcribed on your machine.",
    bar: "Audio captured locally",
    start: "12%",
    width: "48%",
  },
  {
    index: "03",
    title: "Release",
    body: "Let the key go. Recognition and optional cleanup run before anything is inserted.",
    bar: "Recognise + clean",
    start: "60%",
    width: "24%",
  },
  {
    index: "04",
    title: "Insert",
    body: "Clean text appears at the cursor in the app you were already using.",
    bar: "Text in focused app",
    start: "84%",
    width: "16%",
  },
];

const specs = [
  ["Desktop", "GNOME or KDE · Wayland or X11"],
  ["Runtime", "Python 3.10–3.14 · GTK 3"],
  ["Optional UI", "Rust 1.99.1+ for Rune"],
  ["Models", "About 1.7 GB, downloaded once"],
  ["Account", "None"],
  ["License", "MIT for linux/ · upstream GPL-3.0"],
];

const repo = "https://github.com/Lothnic/falco";

function FalcoMark({ className = "" }: { className?: string }) {
  return (
    <svg className={className} viewBox="0 0 40 40" aria-hidden="true" focusable="false">
      <circle cx="20" cy="20" r="18.4" fill="none" stroke="currentColor" strokeWidth="1.1" />
      <path
        d="M19.5 8.6c-4.4 0-7.5 3-7.5 7.2 0 2.3 1.1 4 3 5.2v5.6l4.5 3.7 4.5-3.7V21c1.9-1.2 3-2.9 3-5.2 0-4.2-3.1-7.2-7.5-7.2Z"
        fill="currentColor"
      />
      <path d="M26.6 14.2 33 16.2l-6.4 2.4Z" fill="var(--accent)" />
      <circle cx="17" cy="14.8" r="1.25" fill="var(--paper)" />
    </svg>
  );
}

function KeycapArt() {
  return (
    <svg className="keycap-art" viewBox="0 0 660 600" role="img" aria-labelledby="keycap-title">
      <title id="keycap-title">An isometric drawing of the Falco dictation key</title>
      <defs>
        <linearGradient id="kc-top-grad" x1="0" y1="0" x2="0.4" y2="1">
          <stop offset="0" className="kc-stop-top-a" />
          <stop offset="1" className="kc-stop-top-b" />
        </linearGradient>
        <linearGradient id="kc-left-grad" x1="0" y1="0" x2="0" y2="1">
          <stop offset="0" className="kc-stop-left-a" />
          <stop offset="1" className="kc-stop-left-b" />
        </linearGradient>
        <linearGradient id="kc-right-grad" x1="0" y1="0" x2="0" y2="1">
          <stop offset="0" className="kc-stop-right-a" />
          <stop offset="1" className="kc-stop-right-b" />
        </linearGradient>
        <radialGradient id="kc-dish-grad" cx="34%" cy="26%" r="85%">
          <stop offset="0" className="kc-stop-dish-a" />
          <stop offset="0.55" className="kc-stop-dish-b" />
          <stop offset="1" className="kc-stop-dish-c" />
        </radialGradient>
        <radialGradient id="kc-glow-grad" cx="50%" cy="50%" r="50%">
          <stop offset="0" className="kc-stop-glow-a" />
          <stop offset="1" className="kc-stop-glow-b" />
        </radialGradient>
        <filter id="kc-shadow-blur" x="-40%" y="-40%" width="180%" height="180%">
          <feGaussianBlur stdDeviation="17" />
        </filter>
      </defs>

      <g className="kc-dim">
        <path className="kc-dim-line" d="M48 44h544" />
        <path className="kc-dim-line" d="M48 34v16M592 34v16M592 230h20M592 342h20" />
        <path className="kc-arrow" d="M48 44l13-5v10z" />
        <path className="kc-arrow" d="M592 44l-13-5v10z" />
        <path className="kc-dim-line" d="M612 230v112" />
        <path className="kc-arrow" d="M612 230l-5 13h10z" />
        <path className="kc-arrow" d="M612 342l-5-13h10z" />
        <text x="320" y="28" textAnchor="middle">
          19.05 MM · 1U
        </text>
        <text x="630" y="286" textAnchor="middle" transform="rotate(-90 630 286)">
          4.0 MM
        </text>
      </g>

      <path className="kc-shadow" d="M66 430 322 560 590 418 334 288Z" filter="url(#kc-shadow-blur)" />
      <path className="kc-shadow-ring" d="M66 430 322 560 590 418 334 288Z" />

      <path className="kc-side kc-side-left" d="M48 230 320 364V476L48 342Z" fill="url(#kc-left-grad)" />
      <path className="kc-side kc-side-right" d="M320 364 592 230V342L320 476Z" fill="url(#kc-right-grad)" />
      <path className="kc-side-seam" d="M320 364V476" />
      <path className="kc-top" d="M320 96 592 230 320 364 48 230Z" fill="url(#kc-top-grad)" />
      <path className="kc-top-highlight" d="M48 230 320 96 592 230" />
      <path className="kc-top-shade" d="M48 230 320 364 592 230" />

      <g className="kc-dish">
        <path d="M320 115 554 230 320 345 86 230Z" fill="url(#kc-dish-grad)" />
        <path className="kc-dish-edge-light" d="M86 230 320 115 554 230" />
        <path className="kc-dish-edge-shadow" d="M86 230 320 345 554 230" />
        <path className="kc-dish-inner" d="M320 124 540 230 320 336 100 230Z" />
      </g>

      <circle className="kc-glow" cx="320" cy="236" r="92" fill="url(#kc-glow-grad)" />

      <text className="kc-brand" x="320" y="163" textAnchor="middle">
        FALCO
      </text>
      <text className="kc-sub" x="320" y="178" textAnchor="middle">
        DICTATION KEY · 01
      </text>

      <g className="kc-wave">
        <path d="M291 218v28M281 223v18M271 227v10M349 218v28M359 223v18M369 227v10" />
      </g>
      <g className="kc-mic">
        <rect x="306" y="193" width="28" height="50" rx="14" />
        <path d="M291 228a29 29 0 0 0 58 0M320 257v15M307 272h26" />
      </g>
      <text className="kc-hold" x="320" y="316" textAnchor="middle">
        HOLD TO TALK
      </text>

      <g className="kc-fine kc-stamp">
        <circle cx="40" cy="578" r="3" />
        <text x="52" y="582">
          LOCAL / ON-DEVICE
        </text>
      </g>

      <g className="kc-compass">
        <circle cx="612" cy="558" r="19" />
        <path className="kc-compass-needle" d="M612 544 618 562 612 558 606 562Z" />
        <path d="M612 536v6M612 574v6M590 558h6M628 558h6" />
        <text x="612" y="592" textAnchor="middle">
          LOCAL
        </text>
      </g>
    </svg>
  );
}

function CaptureArt() {
  return (
    <svg className="stage-svg" viewBox="0 0 160 96" aria-hidden="true">
      <g className="d-line">
        <rect x="68" y="10" width="18" height="32" rx="9" />
        <path d="M56 34a21 21 0 0 0 42 0M77 55v14M66 69h22" />
      </g>
      <g className="d-accent">
        <path d="M22 48v-8M30 52V28M38 48V36M46 53V22M114 48v-8M122 52V28M130 48V36M138 53V22" />
      </g>
      <text className="d-label" x="80" y="91" textAnchor="middle">
        MIC IN
      </text>
    </svg>
  );
}

function TranscribeArt() {
  return (
    <svg className="stage-svg" viewBox="0 0 160 96" aria-hidden="true">
      <g className="d-line">
        <rect x="30" y="24" width="100" height="48" />
        <path className="d-faint" d="M30 40h100M30 56h100M55 24v48M80 24v48M105 24v48" />
      </g>
      <g className="d-chip">
        <circle cx="46" cy="40" r="2.5" />
        <circle cx="71" cy="40" r="2.5" />
        <circle cx="96" cy="40" r="2.5" />
        <circle cx="121" cy="40" r="2.5" />
        <circle cx="46" cy="56" r="2.5" />
        <circle cx="71" cy="56" r="2.5" />
        <circle cx="96" cy="56" r="2.5" />
        <circle cx="121" cy="56" r="2.5" />
      </g>
      <g className="d-accent">
        <path d="M16 48h14M130 48h14M30 64v8M80 72v8M130 64v8" />
      </g>
      <text className="d-label" x="80" y="91" textAnchor="middle">
        PARAKEET / WHISPER
      </text>
    </svg>
  );
}

function RefineArt() {
  return (
    <svg className="stage-svg" viewBox="0 0 160 96" aria-hidden="true">
      <g className="d-line">
        <path d="M18 26h124M18 42h58M18 58h108M18 74h74" />
      </g>
      <g className="d-accent">
        <path d="M84 42h48M84 34h48" strokeDasharray="3 3" />
        <rect x="84" y="30" width="48" height="16" fill="none" />
        <path d="M132 54l6-6M138 54l-6-6" />
      </g>
      <text className="d-label" x="80" y="91" textAnchor="middle">
        LOCAL CLEANUP
      </text>
    </svg>
  );
}

function InsertArt() {
  return (
    <svg className="stage-svg" viewBox="0 0 160 96" aria-hidden="true">
      <g className="d-line">
        <rect x="22" y="18" width="116" height="48" />
        <path d="M22 30h116" />
        <circle cx="29" cy="24" r="1.6" />
        <circle cx="35" cy="24" r="1.6" />
        <circle cx="41" cy="24" r="1.6" />
        <path className="d-faint" d="M34 42h56M34 52h72" />
      </g>
      <g className="d-accent">
        <path d="M100 38v20" />
        <path d="M68 74h24M62 80h36" />
      </g>
      <text className="d-label" x="80" y="92" textAnchor="middle">
        FOCUSED APP
      </text>
    </svg>
  );
}

function OverlayArt() {
  return (
    <svg className="overlay-art" viewBox="0 0 460 552" role="img" aria-labelledby="overlay-title">
      <title id="overlay-title">A drawing of the Rune dashboard with the recording overlay</title>
      <g className="ov-screen">
        <rect x="30" y="24" width="400" height="270" />
        <path d="M30 52h400" />
        <circle cx="44" cy="38" r="2" />
        <circle cx="52" cy="38" r="2" />
        <circle cx="60" cy="38" r="2" />
        <path className="d-faint" d="M44 66v212M44 66h88M44 132h88M44 198h88" />
        <rect x="54" y="76" width="48" height="10" />
        <rect x="54" y="142" width="38" height="8" />
        <rect x="54" y="208" width="44" height="8" />
        <rect x="146" y="70" width="260" height="76" />
        <path className="d-faint" d="M156 88h80M156 102h124M156 124h52M292 88h42M292 102h62" />
        <rect x="146" y="160" width="124" height="88" />
        <rect x="282" y="160" width="124" height="88" />
        <path className="d-faint" d="M156 178h52M156 192h72M156 214h44M292 178h52M292 192h72M292 214h44" />
        <path className="ov-baseline" d="M146 263h260" />
      </g>
      <g className="ov-overlay">
        <rect x="82" y="326" width="296" height="62" rx="8" />
        <g className="ov-wave">
          <path d="M110 358v-8M122 360v-14M134 356v-4M146 361v-22M158 357v-8M170 360v-18M182 355v-4M194 361v-24M206 357v-10M218 360v-16M230 356v-6M242 361v-20M254 357v-12M266 360v-18M278 356v-4M290 361v-22M302 357v-8M314 360v-14M326 355v-4M338 361v-20M350 357v-10" />
        </g>
        <text x="110" y="379">
          LISTENING
        </text>
        <text x="362" y="379" textAnchor="end">
          00:04.2
        </text>
      </g>
      <g className="ov-dim">
        <path d="M82 312v-16h296v16M82 304h10M368 304h10" />
        <text x="230" y="299" textAnchor="middle">
          RECORDING OVERLAY · 296 PX
        </text>
        <path d="M30 430h400M30 422v16M430 422v16" />
        <text x="230" y="452" textAnchor="middle">
          RUNE DASHBOARD / OVERLAY
        </text>
      </g>
      <g className="kc-fine">
        <path d="M378 326 410 306" />
        <text x="414" y="303">
          DETAIL A
        </text>
        <path d="M30 470v46h400v-46" />
        <text x="230" y="500" textAnchor="middle">
          EXPERIMENTAL · RUST SIDECAR
        </text>
      </g>
    </svg>
  );
}

function NetworkArt() {
  return (
    <svg className="network-art" viewBox="0 0 520 340" role="img" aria-labelledby="network-title">
      <title id="network-title">A network diagram showing dictation staying inside the local machine</title>
      <g className="net-boundary">
        <rect x="18" y="44" width="328" height="250" strokeDasharray="5 5" />
        <text x="32" y="66">
          YOUR MACHINE
        </text>
      </g>
      <g className="d-line">
        <rect x="102" y="128" width="112" height="72" />
        <rect x="258" y="128" width="64" height="72" />
        <rect x="46" y="152" width="28" height="20" rx="3" />
        <path d="M46 178a18 18 0 0 0 28 0M60 184v10M52 194h16" />
      </g>
      <g className="d-accent">
        <path d="M74 162h28M214 164h44M322 164h22" />
        <path d="M208 160l6 4-6 4M316 160l6 4-6 4" />
      </g>
      <g className="net-labels">
        <text x="60" y="222" textAnchor="middle">
          MIC
        </text>
        <text x="158" y="222" textAnchor="middle">
          PARAKEET
        </text>
        <text x="158" y="236" textAnchor="middle">
          + REFINER
        </text>
        <text x="290" y="222" textAnchor="middle">
          FOCUSED
        </text>
        <text x="290" y="236" textAnchor="middle">
          APP
        </text>
      </g>
      <g className="net-cloud">
        <path d="M410 136a26 26 0 0 1 50 0 21 21 0 0 1 21 21h-92a21 21 0 0 1 21-21Z" />
        <path className="net-cross" d="M424 124l58 58M482 124l-58 58" />
        <text x="458" y="196" textAnchor="middle">
          CLOUD
        </text>
        <text x="458" y="210" textAnchor="middle">
          NOT USED
        </text>
      </g>
      <g className="net-route">
        <path d="M352 164h40" strokeDasharray="4 4" />
        <text x="374" y="154" textAnchor="middle">
          0 B
        </text>
        <text x="374" y="224" textAnchor="middle">
          SENT
        </text>
      </g>
      <g className="kc-fine">
        <path d="M18 316h328M18 308v16M346 308v16" />
        <text x="182" y="334" textAnchor="middle">
          AUDIO + TEXT STAY LOCAL
        </text>
      </g>
    </svg>
  );
}

export default function Home() {
  return (
    <>
      <a className="skip-link" href="#main">
        Skip to content
      </a>
      <header className="site-header">
        <div className="shell header-inner">
          <a className="brand" href="#top" aria-label="Falco home">
            <FalcoMark className="brand-mark" />
            <span className="brand-name">Falco</span>
            <span className="brand-sub">Local dictation</span>
          </a>
          <nav className="header-nav" aria-label="Primary navigation">
            {nav.map((item) => (
              <a key={item.href} href={item.href}>
                {item.label}
              </a>
            ))}
          </nav>
          <div className="header-actions">
            <ThemeToggle />
            <a className="btn btn-ink btn-small" href="#install">
              Install
            </a>
          </div>
        </div>
      </header>

      <main id="main">
        <section className="hero drafting-grid" id="top">
          <div className="shell">
            <div className="hero-meta">
              <p>
                <span className="meta-rule" aria-hidden="true" />
                Voice input · Linux · Wayland + X11
              </p>
              <p className="hero-meta-right">
                Fig. 01 — Signal path
                <br />
                <span>Parakeet Ultra v3 · Local</span>
              </p>
            </div>

            <div className="hero-grid">
              <div className="hero-copy">
                <h1>
                  Speak.
                  <br />
                  It types.
                  <br />
                  Nothing
                  <br />
                  <span className="accent">leaves.</span>
                </h1>
                <p className="hero-lede">
                  Falco is a local dictation app for Linux. Hold a key, speak, and clean text appears in the
                  app you are already using. Recognition runs on your machine, not a server.
                </p>
                <div className="hero-actions">
                  <a className="btn btn-ink" href="#install">
                    Install Falco <span aria-hidden="true">→</span>
                  </a>
                  <a className="link-underline" href={`${repo}/blob/main/linux/README.md`}>
                    Read the Linux guide
                  </a>
                </div>
                <p className="hero-note">Free · MIT · No account</p>
              </div>

              <figure className="hero-figure">
                <div className="figure-head">
                  <span>Fig. 01 — Dictation key</span>
                  <span>Scale 1:1</span>
                </div>
                <KeycapArt />
                <figcaption>
                  <span>Hold / speak / release</span>
                  <span>Rev. 0.1</span>
                </figcaption>
              </figure>
            </div>

            <DictationDemo />
          </div>
        </section>

        <section className="stats" aria-label="Falco at a glance">
          <div className="shell stats-grid">
            {stats.map((stat) => (
              <div className="stat" key={stat.label}>
                <p className="stat-value">
                  {stat.value}
                  {stat.unit ? <span>{stat.unit}</span> : null}
                </p>
                <p className="stat-label">{stat.label}</p>
              </div>
            ))}
          </div>
        </section>

        <section className="section signal" id="signal">
          <div className="shell">
            <div className="section-head">
              <p className="eyebrow">01 / Signal path</p>
              <h2>
                From keypress
                <br />
                to <span className="accent">clean text.</span>
              </h2>
              <p className="section-side">
                Four stages, one machine. Nothing is sent away for processing, and the microphone closes as
                soon as the key comes up.
              </p>
            </div>

            <div className="panel signal-board">
              <div className="panel-meta">
                <span>Fig. 02 — Dictation pipeline</span>
                <span>All stages local · Not to scale</span>
              </div>
              <div className="signal-stages">
                {stages.map((stage, index) => (
                  <article className="stage" key={stage.label}>
                    <div className="stage-figure">
                      {index === 0 ? <CaptureArt /> : null}
                      {index === 1 ? <TranscribeArt /> : null}
                      {index === 2 ? <RefineArt /> : null}
                      {index === 3 ? <InsertArt /> : null}
                    </div>
                    <p className="stage-label">{stage.label}</p>
                    <h3>{stage.title}</h3>
                    <p>{stage.body}</p>
                  </article>
                ))}
              </div>
              <div className="signal-foot">
                <span>Audio in</span>
                <span>No network hop</span>
                <span>Text out</span>
              </div>
            </div>
          </div>
        </section>

        <section className="section capabilities" id="capabilities">
          <div className="shell">
            <div className="section-head">
              <p className="eyebrow">02 / Capabilities</p>
              <h2>
                Six things it does
                <br />
                without <span className="accent">a cloud.</span>
              </h2>
              <p className="section-side">
                A small app with a narrow job: take the words you say and put them where the cursor is.
              </p>
            </div>

            <div className="capabilities-layout">
              <div className="cap-table">
                <div className="cap-head" aria-hidden="true">
                  <span>No.</span>
                  <span>Capability</span>
                  <span>Detail</span>
                  <span>Mode</span>
                </div>
                {capabilities.map((capability, index) => (
                  <article className="cap-row" key={capability.title}>
                    <span className="cap-index">{String(index + 1).padStart(2, "0")}</span>
                    <h3>{capability.title}</h3>
                    <p>{capability.body}</p>
                    <span className="cap-meta">{capability.meta}</span>
                  </article>
                ))}
              </div>

              <aside className="cap-art panel">
                <div className="panel-meta">
                  <span>Fig. 03 — Rune interface</span>
                  <span>Detail A</span>
                </div>
                <OverlayArt />
                <div className="cap-art-foot">
                  <span>Recording overlay</span>
                  <span>Experimental</span>
                </div>
              </aside>
            </div>
          </div>
        </section>

        <section className="section privacy" id="privacy">
          <div className="shell">
            <div className="privacy-head">
              <p className="eyebrow">03 / Privacy</p>
              <div>
                <h2 className="pullquote">
                  <span className="quote-mark" aria-hidden="true">
                    “
                  </span>
                  Your voice never leaves the room.
                  <span className="quote-mark" aria-hidden="true">
                    ”
                  </span>
                </h2>
                <p className="quote-attrib">— Falco’s default network policy</p>
              </div>
            </div>

            <div className="privacy-grid">
              <div className="privacy-copy">
                <p>
                  Speech recognition, cleanup rules, and the optional refiner all run on the same machine
                  that captured the audio. Falco needs no account, no API key, and no connection once its
                  models are on disk.
                </p>
                <p>
                  That makes dictation work on a plane, in a locked-down office, or with the network cable
                  out. The model download is the only network step.
                </p>
                <ul className="privacy-list">
                  <li>Audio and transcripts stay on the machine.</li>
                  <li>Recent dictations are session data, not a permanent history.</li>
                  <li>No account, API key, or metered minutes.</li>
                  <li>Models are downloaded once and used offline.</li>
                </ul>
              </div>
              <div className="privacy-art panel">
                <div className="panel-meta">
                  <span>Fig. 04 — Network boundary</span>
                  <span>0 B sent</span>
                </div>
                <NetworkArt />
                <div className="cap-art-foot">
                  <span>Local by default</span>
                  <span>Offline ready</span>
                </div>
              </div>
            </div>
          </div>
        </section>

        <section className="section process" id="process">
          <div className="shell">
            <div className="section-head">
              <p className="eyebrow">04 / Process</p>
              <h2>
                One key.
                <br />
                Four <span className="accent">steps.</span>
              </h2>
              <p className="section-side">
                The same motion in every app: press, speak, release, keep working. No window switching and no
                copy-paste.
              </p>
            </div>

            <div className="panel process-board">
              <div className="panel-meta">
                <span>Fig. 05 — Dictation sequence</span>
                <span>Sequence, not to scale</span>
              </div>
              <div className="process-header" aria-hidden="true">
                <span />
                <span />
                <div className="process-axis">
                  <span>Start</span>
                  <span>Hold</span>
                  <span>Release</span>
                  <span>Text</span>
                </div>
              </div>
              {processRows.map((row) => (
                <div className="process-row" key={row.index}>
                  <span className="process-index">{row.index}</span>
                  <div className="process-copy">
                    <h3>{row.title}</h3>
                    <p>{row.body}</p>
                  </div>
                  <div className="process-track">
                    <div
                      className="process-bar"
                      style={{ left: row.start, width: row.width }}
                    >
                      {row.bar}
                    </div>
                  </div>
                </div>
              ))}
            </div>
          </div>
        </section>

        <section className="section install" id="install">
          <div className="shell">
            <div className="section-head">
              <p className="eyebrow">05 / Installation</p>
              <h2>
                A Linux desktop.
                <br />
                A microphone.
                <br />
                <span className="accent">That’s the list.</span>
              </h2>
              <p className="section-side">
                Falco installs from source into your user account. Ubuntu is the primary tested distribution;
                GNOME and KDE Plasma on Wayland or X11 are the intended environments.
              </p>
            </div>

            <div className="install-layout">
              <div className="install-steps">
                <CopyCommand
                  index="01"
                  label="Quick install"
                  command="curl -fsSL https://falco.lothnic.dev/install.sh | bash"
                  note="Installs the Linux dependencies with sudo, then Falco under ~/.local/share/falco-app. Use --no-deps to manage packages yourself."
                />
                <CopyCommand
                  index="02"
                  label="Manual packages"
                  command="sudo apt install python3 python3-venv python3-pip python3-gi python3-gi-cairo python3-dbus python3-evdev gir1.2-gtk-3.0 gir1.2-ayatanaappindicator3-0.1 libportaudio2 wl-clipboard"
                  note="Ubuntu and Debian package names. PyGObject, D-Bus, evdev, PortAudio, and wl-clipboard are required."
                />
                <CopyCommand
                  index="03"
                  label="From a checkout"
                  command={`git clone ${repo}.git && cd falco && ./linux/install.sh`}
                  note="Installs under ~/.local/share/falco-app and adds ~/.local/bin/falco. The installer refuses to overwrite an existing installation."
                />
                <p className="install-note">
                  Optional: for the Rune dashboard and recording overlay, append{" "}
                  <code>bash -s -- --with-rune</code> to the quick install command. Without it,
                  Falco uses the GTK tray interface.
                </p>
              </div>

              <aside className="spec-panel panel">
                <div className="panel-meta">
                  <span>Specification / Falco 0.1</span>
                  <span>Sheet A-001</span>
                </div>
                <dl className="spec-list">
                  {specs.map(([term, value]) => (
                    <div className="spec-row" key={term}>
                      <dt>{term}</dt>
                      <dd>{value}</dd>
                    </div>
                  ))}
                </dl>
                <div className="spec-status">
                  <span className="status-dot" aria-hidden="true" />
                  <div>
                    <strong>Early source package</strong>
                    <span>Transcription and cleanup tested on Ubuntu</span>
                  </div>
                </div>
              </aside>
            </div>
          </div>
        </section>

        <section className="closing">
          <div className="shell closing-inner">
            <div>
              <p className="eyebrow">06 / Ready</p>
              <h2>
                Stop typing.
                <br />
                <span className="accent">Start talking.</span>
              </h2>
            </div>
            <div className="closing-action">
              <a className="btn btn-ink" href="#install">
                Install Falco <span aria-hidden="true">→</span>
              </a>
              <p>Source available on GitHub · MIT for linux/</p>
            </div>
          </div>
        </section>
      </main>

      <footer className="footer drafting-grid">
        <div className="shell">
          <div className="footer-top">
            <div className="footer-brand">
              <a className="brand" href="#top" aria-label="Falco home">
                <FalcoMark className="brand-mark" />
                <span className="brand-name">Falco</span>
              </a>
              <p>
                Local dictation for Linux. Built on TuxTalk, in a fork of Phonon, with the optional Phonon
                refiner for cleanup.
              </p>
            </div>
            <nav className="footer-links" aria-label="Project links">
              <a href={repo}>GitHub repository</a>
              <a href={`${repo}/blob/main/linux/README.md`}>Linux guide</a>
              <a href="https://huggingface.co/Infatoshi/phonon-refiner-1.7b">Refiner model</a>
              <a href="https://github.com/Infatoshi/phonon">Upstream Phonon</a>
            </nav>
          </div>

          <div className="title-block" aria-label="Project title block">
            <div>
              <span>Project</span>
              <strong>Falco</strong>
            </div>
            <div>
              <span>Drawing</span>
              <strong>Local dictation</strong>
            </div>
            <div>
              <span>Sheet</span>
              <strong>A-001</strong>
            </div>
            <div>
              <span>Revision</span>
              <strong>0.1</strong>
            </div>
            <div>
              <span>Scale</span>
              <strong>1:1</strong>
            </div>
            <div>
              <span>License</span>
              <strong>MIT / GPL-3.0</strong>
            </div>
          </div>

          <div className="footer-bottom">
            <p>
              Falco is an experimental community app. Not an official Phonon or TuxTalk release. Model weights
              keep their own licenses.
            </p>
            <p>© 2026 · Made for Linux</p>
          </div>
        </div>
      </footer>
    </>
  );
}
