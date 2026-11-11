import assert from "node:assert/strict";
import { execFileSync } from "node:child_process";
import { readFile } from "node:fs/promises";
import test from "node:test";
import { fileURLToPath } from "node:url";

test("renders the Falco landing page", async () => {
  const html = await readFile(new URL("../.next/server/app/index.html", import.meta.url), "utf8");

  assert.match(html, /<title>Falco: local dictation for Linux<\/title>/i);
  assert.match(html, /data-theme="dark"/);
  assert.match(html, /Speak\.<br\/>It types\.<br\/>Nothing<br\/>/);
  assert.match(html, /Your voice never leaves the room\./);
  assert.match(html, /Six things it does/);
  assert.match(html, /Parakeet Ultra v3/);
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
  assert.match(html, /Wayland or X11/);
  assert.match(html, /Loading model/);
  assert.doesNotMatch(html, /Whistle/i);
  assert.doesNotMatch(html, /Fast\. Local\./);
  assert.doesNotMatch(html, /brew install --cask infatoshi\/tap\/phonon/);
  assert.doesNotMatch(html, /Get Phonon for macOS/);
  assert.doesNotMatch(html, /Windows beta/);
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
