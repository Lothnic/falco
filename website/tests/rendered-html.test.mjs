import assert from "node:assert/strict";
import { execFileSync } from "node:child_process";
import { readFile } from "node:fs/promises";
import test from "node:test";
import { fileURLToPath } from "node:url";

test("renders the Falco landing page", async () => {
  const html = await readFile(new URL("../.next/server/app/index.html", import.meta.url), "utf8");

  assert.match(html, /<title>Falco 2\.6\.0: local dictation for Linux<\/title>/i);
  assert.match(html, /data-theme="dark"/);
  assert.match(html, /Speak\.<br\/>It types\.<br\/>Nothing<br\/>/);
  assert.match(html, /Your voice never leaves the room\./);
  assert.match(html, /Seven things it does/);
  assert.match(html, /Parakeet Ultra v3/);
  assert.match(html, /About 670 MB for Parakeet Ultra v3/);
  assert.match(html, /About 1 GB extra, including its engine/);
  assert.match(html, /Optional local cleanup/);
  assert.match(html, /curl -fsSL https:\/\/falco\.lothnic\.dev\/install\.sh \| bash/);
  assert.match(html, /Copy quick install command/);
  assert.match(html, /git clone https:\/\/github\.com\/Lothnic\/falco\.git/);
  assert.match(html, /sudo apt install python3/);
  assert.match(html, /Copy manual packages command/);
  assert.match(html, /Copy from a checkout command/);
  assert.match(html, /Early source package/);
  assert.match(html, /Not an official Phonon or TuxTalk release\./);
  assert.match(html, /Rune dashboard/);
  assert.match(html, /Command Mode/);
  assert.match(html, /Wayland or X11/);
  assert.match(html, /Loading model/);
  assert.doesNotMatch(html, /Whistle/i);
  assert.doesNotMatch(html, /Fast\. Local\./);
  assert.doesNotMatch(html, /brew install --cask infatoshi\/tap\/phonon/);
  assert.doesNotMatch(html, /Get Phonon for macOS/);
  assert.doesNotMatch(html, /Windows beta/);
});

test("publishes versioned refiner benchmarks with their measurement scope", async () => {
  const html = await readFile(new URL("../.next/server/app/index.html", import.meta.url), "utf8");
  const text = html.replace(/<[^>]*>/g, "").replace(/<!--.*?-->/g, "");
  const data = JSON.parse(await readFile(new URL("../public/benchmarks/refiner-2.5-linux.json", import.meta.url), "utf8"));
  const source = JSON.parse(await readFile(new URL("../../docs/benchmarks/refiner-2.5-linux.json", import.meta.url), "utf8"));
  assert.deepEqual(data, source);
  assert.equal(data.baseline.length, 8);
  assert.equal(data.accelerated.length, 8);
  for (const [index, row] of data.baseline.entries()) {
    assert.equal(row.answer, data.accelerated[index].answer);
  }
  assert.match(html, /id="benchmarks"/);
  assert.match(text, /32%/);
  assert.match(text, /1\.47× faster/);
  assert.match(text, /371 ms/);
  assert.match(text, /198 ms/);
  assert.match(text, /Refiner HTTP requests only/);
  assert.match(text, /very long outputs and contexts have not been tested/);
  assert.match(text, /RTX 4060 Laptop GPU, 8 GB/);
  assert.match(html, /releases\/tag\/v2\.6\.0/);
  assert.match(text, /215 MB/);
  assert.doesNotMatch(text, /Specification \/ Falco 0\.1|Rev\. 0\.1|until the first release/);
});

test("website, app and Rune identify the same release", async () => {
  const pkg = JSON.parse(await readFile(new URL("../package.json", import.meta.url), "utf8"));
  const release = await readFile(new URL("../app/release.ts", import.meta.url), "utf8");
  const app = await readFile(new URL("../../linux/src/localdictation/__init__.py", import.meta.url), "utf8");
  const pythonPackage = await readFile(new URL("../../linux/pyproject.toml", import.meta.url), "utf8");
  const rune = await readFile(new URL("../../linux/rune-overlay/Cargo.toml", import.meta.url), "utf8");
  assert.equal(pkg.version, "2.6.0");
  assert.ok(release.includes(`version = "${pkg.version}"`));
  assert.ok(app.includes(`__version__ = "${pkg.version}"`));
  assert.ok(pythonPackage.includes(`version = "${pkg.version}"`));
  assert.ok(rune.includes(`version = "${pkg.version}"`));
});

test("ships a curl-to-bash installer", async () => {
  const path = fileURLToPath(new URL("../public/install.sh", import.meta.url));
  const source = await readFile(path, "utf8");

  execFileSync("bash", ["-n", path]);

  const help = execFileSync("bash", [path, "--help"], { encoding: "utf8" });
  assert.match(help, /Usage: install\.sh/);
  assert.match(help, /--with-rune/);
  assert.match(help, /--no-deps/);

  assert.match(source, /curl -fL --proto '=https'/);
  assert.match(source, /bash linux\/install\.sh/);
  assert.match(source, /github\.com\/\$REPO\/archive\/\$REF/);
});
