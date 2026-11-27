# Falco website

Landing page for [Falco](https://github.com/Lothnic/falco), the local dictation app for Linux.

Current release: **2.6.0 — Command Mode**. Version displays and release links
come from `app/release.ts`. The Linux benchmark section derives its values from
`public/benchmarks/refiner-2.5-linux.json`, a published copy of the measured data
in `../docs/benchmarks/`. Keep both JSON files identical when updating evidence.

```sh
npm install
npm run dev
npm test
```

`npm test` builds the site and checks the rendered HTML for the Falco copy, install commands, and the `public/install.sh` script.

The production site is the Vercel project `falco` at `falco.lothnic.dev`, deployed
from this directory. App release notes and benchmark methodology are in
`../docs/releases/v2.6.0.md` and `../docs/benchmarks/README.md`.
