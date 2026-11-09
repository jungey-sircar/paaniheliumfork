# Building, iterating and verifying Paani

Paani does not replace Helium's build tooling; it adds one layer in front of
it. This document is the runbook for that layer on the machine it was
developed on (Windows 11 25H2, i5-12450H, 16 GB RAM, builds on a mechanical
`E:`). Every duration in here is measured, not estimated.

## What the Paani layer consists of

| Part | Location | What it does |
|---|---|---|
| Paani-owned sources | `paani-windows/src/**` | The ad blocker (`chrome/browser/paani/adblock`), the `chrome://paani` WebUI (C++, mojom, Lit). Copied verbatim into `build/src` by the `sources` step, which byte-compares so unchanged files do not refresh mtimes |
| Patch series | `paani-windows/patches/paani/windows/*.patch` (14 patches, quilt format) | Every edit to an upstream Chromium/Helium file: branding, binary rename, scheme registration, water theme, Mica backdrop, native frame, versioning, the ad-block hook, the WebUI wiring |
| Name substitution | `utils/paani_name_substitution.py` | 1,303 files rewritten from Chrome/Helium naming to Paani where the identifier is user-visible or asset-level |
| Assets | `paani-windows/resources` + `utils/paani_icons.py` | Waterdrop icons, installer branding |
| Drivers | `paani-windows/build/patchwork/run_paani_step.py`, `run_build.py` | Run one prep step, or build, with the MSVC toolchain environment and a log file |

`build.py` runs the whole layer; `run_paani_step.py` runs one step and writes
the same marker file, so a later `build.py --paani-only` skips it. That
granularity exists because a full relink costs about an hour and a half and you
do not want to discover a bad patch at the link stage.

## Requirements

* Visual Studio Build Tools 2022 with the **C++ ATL** component, and Windows
  SDK **10.0.28000.0** — Chromium 156 pins that SDK and `build.py` fails fast
  if it is missing.
* CPython 3.13 as `python`. Chromium's codegen actions must not pick up an
  MSYS2 `python3`; `build.py` puts its own `python3.exe` on the build PATH for
  that reason.
* Not administrator, no Developer Mode: anything needing symlinks or writes
  under `C:\Python313` needs an explicit UAC prompt.

## First build from a Helium release tag

```sh
cd paani-windows
python build.py --paani-only                       # prep layer + full build
# or step by step, which is what iterating uses:
python build/patchwork/run_paani_step.py sources
python build/patchwork/run_paani_step.py patches
python build/patchwork/run_paani_step.py substitute
python build/patchwork/run_paani_step.py version
python build/patchwork/run_paani_step.py resources
python build/patchwork/run_paani_step.py gn
python build/patchwork/run_build.py -j 8 -k 0 -C out/Default chrome chromedriver setup mini_installer
```

`-j 8` is the measured fit for this box: at `-j 6` CPU sat at 63%, so the build
was starved rather than limited. Free RAM, not the job count, is what breaks
runs — see the landmines below.

## Iterating: which change needs which cost

Measured on 2026-11-06/07 for `chrome chromedriver setup mini_installer` in
`out/Default`:

| Change | Cost | Notes |
|---|---|---|
| `paani-windows/src/**` code edit, then `sources` + relink | ~1 h 12 m | One 21-minute compile of the touched browser TU (about 9.5 minutes of that is siso reloading its manifest), then the `paani.dll` link, then ~10 packaging steps |
| Upstream-file edit recorded in a patch, then relink | same | The patch has to describe the tree before the build starts (see below) |
| `.grd` / `resource_ids.spec` / `BUILD.gn` edit | `gn` step + relink | `gn gen` itself is seconds; a bad `deps` entry surfaces as "Please update default_resource_ids and add a first id" |
| WebUI TS/CSS edit only | seconds-to-minutes | `node`, `stylelint` and `grit` checks take seconds; use them before committing to a relink |
| Patch text edit only | free | `patch --dry-run` takes seconds |

**Batch every verified edit into one relink.** The scarce resource is the link,
not the compile.

## Patch authoring rules

1. Never run `.paani-patchwork/make_paani_patches.py` against an already
   patched tree: it treats the current file text as pristine and would rewrite
   the series with nonsense.
2. Prefer the `build/patchwork/make_*.py` recorders
   (`make_webui_patch.py`, `make_adblock_hook_patch.py`, `make_mica_patch.py`,
   `make_water_theme_patch.py`, …). They remove the recorded added blocks from
   the current tree to synthesize the pristine text, diff the two, and splice
   the result into the right patch.
3. Prove consistency before building:
   `cd build/src && patch --dry-run -p1 < ../../patches/paani/windows/<name>.patch`
   and the `-R` reverse form. Both must apply cleanly — that is what makes the
   patch a record of the tree rather than a wish.

## Verifying

The ad blocker cannot be judged from a web page. Helium bundles uBlock Origin
as an *incorporated* extension, which is always registered and is not disabled
by `--disable-extensions`, and whose signature is a redirect into
`chrome-extension://…/web_accessible_resources`. So:

* The authoritative counter is Paani's own mojom-reported
  `blockedCount`, which only moves when Paani's `URLLoaderFactory` returned
  `net::ERR_BLOCKED_BY_CLIENT` for the original URL.
* `script.onerror` on a test page is not proof — uBlock's redirect makes the
  script "load".

```sh
# serves verify/www on 127.0.0.1:8731
cd .paani-patchwork/verify
python -m http.server 8731 --bind 127.0.0.1
powershell -NoProfile -ExecutionPolicy Bypass -File launch_diag.ps1 profileX 9341
node cdp_state_json.mjs 9341      # engine stats + rendered text
node cdp_outcomes.mjs 9341 http://127.0.0.1:8731/trackertest.html 25
node verify_paani.mjs 9341        # counter + allowlist, five stages
```

`--enable-logging=stderr` is what makes the engine's health line reachable:

```
Paani: ad blocker ready (8 lists, 5926486 bytes, ~165955 rules)
```

`auto_verify.ps1` waits for a build PID and then runs that whole chain
unattended, appending to `verify/logs/auto_verify_result.txt`.

## Landmines

* **Free the binary lock before linking.** Any running `paani.exe` holds
  `paani.dll` and the `.pak` files open and the link fails with a sharing
  violation.
* **The link is a memory cliff.** `lld-link` for `paani.dll` holds ~6.4 GB
  private and emits a >2 GB PDB at `symbol_level=1`; free RAM can reach
  0.4 GB with heavy paging. Do not "fix" it with `symbol_level=0` — that
  changes every compile command and invalidates the ~55,000 finished steps.
  Close RAM-heavy applications instead, and never sleep during a link.
* **A redirected build log can be stale** while the build is working. Read
  process state and artifact growth, not only the log's mtime.
* **Bash children of the agent's shell are reaped with it**; detached drivers
  have to be started as their own process (that is why the watcher is
  PowerShell and not a shell loop).
* Self-poisoning 0-byte pregenerated `.tlb` files under
  `third_party/win_build_output` appear on a *second* build in the same tree;
  `paani-windows/README.md` has the upstream troubleshooting notes.

## Deliverable

`build/src/out/Default/mini_installer.exe` is the installable artifact. A file
existing is not a result: a build only counts when `run_build.py` printed
`build exit code: 0`, and only artifacts with a timestamp after that build are
the ones that contain the change being claimed. The unmodified Helium 0.20.3.1
binaries are preserved under `build/baseline_helium/` for the A/B measurements.
