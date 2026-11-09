# Paani Browser: licensing and upstream-update strategy

Paani Browser is a personal fork of [Helium](https://github.com/imputnet/helium)
built on the Chromium source tree. It is not a wrapper around an installed
browser and it does not shell out to another engine: it is the browser binary
itself, rebuilt from source with a Paani layer applied on top of an otherwise
unmodified Helium Windows build.

This document records what that means for the licences involved and how the fork
tracks upstream.

## Where Paani code lives

The upstream repositories stay pristine. Nothing Paani writes is committed,
pushed, or proposed to `imputnet/helium` or `imputnet/helium-windows`, and the
`helium-chromium` submodule is never edited. Every Paani-specific change is
confined to `paani-windows/`:

| Location | Contents |
| --- | --- |
| `paani-windows/src/` | Paani-owned source files, copied into the Chromium tree verbatim by `build.py` (the ad blocker, the `chrome://paani` WebUI, the water-palette colour code, the water-drop icons). |
| `paani-windows/patches/paani/` | Patches to *upstream* files, with `series` defining the order. |
| `paani-windows/resources/` | Branding resources: icon sets, resource manifests, the substitution table. |
| `paani-windows/build/patchwork/` | The scripts that generate those patches from the working tree, plus `orig/` pristine copies used as the diff baseline. |

The Chromium working tree under `paani-windows/build/src/` is disposable; it is
regenerated from the archives in `paani-windows/build/download_cache/`.

## Licences

Paani is a derivative work, so the copyleft terms of what it builds on carry
through to any distribution of it.

| Component | Licence | Where it is asserted |
| --- | --- | --- |
| Chromium itself, including Helium's unmodified ports of upstream code | BSD 3-Clause | `build/src/LICENSE` |
| Helium, `helium-windows`, the Helium patches and Helium's own code | GPL-3.0-only | `paani-windows/LICENSE` |
| Code imported from ungoogled-chromium-windows | BSD 3-Clause | `paani-windows/LICENSE.ungoogled_chromium` |
| `adblock-rust` (Brave), vendored as `//third_party/rust/adblock/v0_13` | MPL-2.0 | `build/src/third_party/rust/chromium_crates_io/vendor/adblock-v0_13/LICENSE` |
| uBlock Origin assets, i.e. the filter lists and the `$redirect=` stub payloads Paani's blocker reads | GPL-3.0 | `build/src/third_party/ublock/LICENSE.txt` |
| Individual third-party filter lists (EasyList, pgl.yoyo.org, urlhaus-filter) | each list's own terms | the header block inside each file, and `assets/thirdparties/urlhaus-filter/LICENSE.md` |
| `publicsuffix.org` data used for per-site allowlisting | its own upstream terms | `build/src/third_party/ublock/assets/thirdparties/publicsuffix.org/list` |
| Rust crates pulled in by `adblock-rust` | mostly MIT / Apache-2.0 | `build/src/third_party/rust/chromium_crates_io/vendor/<crate>/LICENSE` |

Paani does not install Helium's uBlock Origin component extension
(`paani-no-ublock-component.patch`), but the assets it ships are still in
`resources.pak` and are still what Paani's engine reads, so the GPL-3.0 notice
in `third_party/ublock/LICENSE.txt` and the per-list headers continue to apply
to any distribution.

Practical consequences:

* The Paani additions to Helium (GPL-3.0) and the changes to Helium's patches are
  GPL-3.0 as well; the whole combined work must be offered under GPL-3.0 when
  distributed.
* MPL-2.0 files (`adblock-rust`, the public-suffix data) keep their file-level
  copyleft: any *modification* to those files has to be made available under
  MPL-2.0. Paani does not modify `adblock-rust` itself - it is used as vendored,
  and all Paani code sits in `chrome/browser/paani/adblock/` behind a C ABI
  shim (`rust/lib.rs`).
* Upstream licence headers and `LICENSE` files are never stripped. Paani's own
  files carry their own headers ("The Paani Browser Authors", Chromium BSD style)
  alongside, not instead of, the inherited notices.
* A distribution of Paani must ship the full Chromium third-party notice set
  (`build/src/third_party/.../LICENSE` and the generated about page), the
  GPL-3.0 text, the MPL-2.0 text for `adblock-rust`, and the filter-list headers.
  `chrome://credits` and `chrome://terms` keep working because the branding
  patches only rename strings.
* The water-drop icon artwork must be original or licence-compatible; whatever
  is under `paani-windows/resources/` is what ships, and its provenance belongs
  in this table before any public release.

Paani is currently built for the author's own machine. That is the least
encumbered position; the obligations above start applying the moment binaries or
sources go to anyone else.

## How the fork tracks upstream

Helium tracks Chromium closely, and security updates matter more to a personal
browser than any Paani feature does. The layer is therefore designed so that an
upstream bump is a scripted sequence, not a rewrite.

### 1. Bump the pins

* The Chromium version comes from the `helium-chromium` submodule and the archive
  names in `paani-windows/downloads.ini` / `downloads.x64.ini`; checking the
  submodule out at the new Helium tag is what actually moves the fork forward.
* `paani-windows/paani_version.txt` holds Paani's own `MAJOR`/`MINOR`/`PATCH`/
  `PLATFORM`. The `paani-versioning` patch writes them into `chrome/VERSION` as
  the `PAANI_*` entries, which is what the browser, the About page and the
  Windows version resource report.
* Nothing in `helium-chromium` is ever edited, only checked out.

### 2. Re-prepare the tree

Run `python build.py` up to the patch stage, or step by step with
`python build/patchwork/run_paani_step.py <sources|patches|version|resources|gn>`.
The unpack and Helium-patch steps are marked in `build/state/*.done`; delete the
marker for a step that needs to run again.

### 3. Re-apply the Paani patch series

`patches/paani/series` is ordered so that later patches can rely on earlier
context:

1. `change-branding` - the Helium Windows branding patch (install paths,
   registry keys, policy templates, version resources).
2. `paani-scheme`, `paani-versioning`, `paani-brand-rename` - identity strings,
   URI scheme, version.
3. `paani-binary-rename` - emits `paani.exe` / `paani.dll` / `paani_proxy.exe`.
   This is also what keeps a Paani build from overwriting a Helium baseline in
   the same output directory.
4. `paani-native-frame`, `paani-webui-logo`, `paani-onboarding-brand` - UI
   surfaces.
5. `paani-adblock`, `paani-adblock-rust-unsafe`, `paani-rust-vendor` - the
   blocker's hooks into the content layer, the `unsafe-code` allowances the Rust
   crate closure needs, and the two vendored Rust targets that have to build
   first.
6. `paani-no-ublock-component` - Helium's uBlock Origin component extension is
   not installed, so the browser has exactly one blocker and one counter.
7. `paani-webui-page`, `paani-water-theme`, `paani-mica-backdrop`,
   `paani-water-backdrop`, `paani-shield-button` - the `chrome://paani` page,
   the colour mixers, the DWM backdrop request, the painted fallback band, and
   the toolbar shield.

`utils/paani_patches.py::apply_series` runs `patch --dry-run --reverse` first, so
re-running it on an already-patched tree is a no-op rather than a double apply.

### 4. Regenerate, don't hand-edit, the patches

Patches are produced by the scripts in `build/patchwork/`
(`make_webui_patch.py`, `make_water_theme_patch.py`, `make_mica_patch.py`,
`make_rust_unsafe_patch.py`) by diffing the working tree against the pristine
copies in `build/patchwork/orig/`. After moving an edit in the tree, re-run the
matching script and commit the new `.patch`. Never edit
`build/src/**` and expect it to survive: that directory is thrown away on the
next bump.

### 5. Validate cheaply before committing to a full build

A full Chromium build on this machine takes hours; the failures that matter are
usually cheap to find:

* `python build/patchwork/check_grit_files.py` parses every `.grd` / `.grdp` /
  `.xtb` file, which catches damage from an interrupted name-substitution pass.
* `python build/patchwork/run_gn.py` (`gn gen`) catches GN-level breakage such as
  a missing entry in `//third_party/lit/v3_0:build_ts`'s visibility list.
* A narrow pre-flight build of just the Paani targets
  (`chrome/browser/resources/paani:resources`,
  `chrome/browser/paani/adblock:paani_adblock`,
  `chrome/browser/ui/webui/paani:paani`, `ui/color:mixers`,
  `chrome/browser/ui/color:mixers`,
  `chrome/browser/ui/views/frame:browser_frame_view_win`) compiles every Paani
  file - Rust closure included - in a fraction of the time.
* Only then the full `chrome chromedriver setup mini_installer` build.

Two ordering rules that have cost real time when broken: the GRIT name
substitution must never run while siso is hashing the tree, and the branding
resource step must run before the build that packages resources.

### 6. Re-verify, don't assume

After a bump, the checks that actually mean something are behavioural:

* `chrome://paani` still reports the blocked-request counter and the allowlist
  survives a restart.
* A known ad URL is still blocked, and an allowlisted host still loads its
  creative.
* The window frame is translucent when Windows transparency is on and solid when
  "Let Windows pick a transparency effect / animations" is off (reduced
  transparency) or forced colours are active.
* Sandbox and certificate validation are untouched. No Paani patch may weaken
  the renderer/utility-process sandbox or relax certificate verification to make
  something convenient, and the water theme must not disable GPU compositing to
  save memory.
* The performance metrics from `docs/PAANI-PHASE1-ARCHITECTURE.md` are re-measured
  against the matching Helium baseline, on the same machine, over the whole
  process tree.

### 7. Keep the baseline

`paani-windows/build/baseline_helium/` holds the SHA-256 of the unmodified Helium
0.20.3.1 binaries plus copies of that build's `helium.7z`,
`helium.packed.7z`, `setup.exe`, and `mini_installer.exe`. Every A/B claim Paani
makes is measured against that copy, so it must not be overwritten by a Paani
build.

## Where the build lands, and what was verified

The build products are in `paani-windows/build/src/out/Default/`:
`paani.exe`, `paani.dll`, `paani_proxy.exe`, `setup.exe` and
`mini_installer.exe`. Running `mini_installer.exe` installs the browser for the
current user under `%LOCALAPPDATA%\Paani\Application\<version>\`, with its
profile in `%LOCALAPPDATA%\Paani\User Data`.

The blocker was verified against a running build, over CDP and the Windows UI
Automation tree. The numbers below come from the four-phase harness
(`.paani-patchwork/verify/verify_shield2.ps1`); each phase closes the other
tabs, lets the counter settle, and resets it before the page load, because the
counter in `chrome://paani` is a **profile** counter and counts the blocks of
every tab:

| Check | Result |
| --- | --- |
| Blocker off | `phase0_off=0` |
| Blocker on (default) | `phase1_blocked=43` (48 in a second run), page title loaded |
| Site allowlisted | `phase2_allowed=14` before the fix, `0` after it (see below) |
| Allowlist entry removed | `phase3_removed=44` - the counter rises again, so phase 2 is the allowlist and not a quiet network |
| Counter is live | 36 → 49 across two reads of the same page |
| Toolbar shield, blocked site | `name='71'` |
| Toolbar shield, allowlisted site | `name='Paani lets ads and trackers through on this site'` |
| Extensions in the browser | no `chrome-extension://` target on the debugging port |

The renderer and the counter count different things, and the difference is
expected: the renderer sees `net::ERR_BLOCKED_BY_CLIENT` only for the requests
that were failed (29 in the measured run), while the counter also counts the
requests answered with a `$redirect=` stub body, which arrive as a normal `200`.

The allowlist is about the *page*, not about the requester. A request is
exempt when the site it was made from is allowlisted **or** when the page that
request was made on is allowlisted; the second half is what makes a third-party
frame on an allowlisted page load its own resources instead of being judged
against its own site. That second check is the fix that took `phase2_allowed`
from 14 to 0.

The third-party extensions question is answered by the same table: Paani has no
ad-blocking extension at all, and the Chrome Web Store component extension
(`AddWebStoreApp()` in `chrome/browser/extensions/component_loader.cc`) is left
in place, so `chrome://extensions` still offers the store for the extensions a
user chooses to add.

`mini_installer.exe` was run after the checks above passed. The installed copy
at `%LOCALAPPDATA%\Paani\Application\1.0.0.1\` is byte-identical to the
verified build (`paani.exe` and `paani.dll` match by SHA-256), and the
**installed** application was re-checked over CDP:
`chrome://extensions-internals` reports
`{"ids":["jfnekidfgkhnfagaabpddmioknbjglgp","mhjfbmdgcfjbbpaeojofohoefgiehjai"],"hasUBlock":false,"hasWebStore":true}`,
so the uBlock Origin component is gone from the installed browser and the
Chrome Web Store component is still there.

## Known scope limits

Honest list of what this fork does *not* do yet, so a future update does not
mistake them for regressions:

* Blocking is network-level only. There is no cosmetic/element hiding, so an ad
  slot can still reserve page space.
* `$redirect=` rules are applied, and `$redirect-rule=` rules are not.
  The 50 stub payloads Helium's uBlock component already ships in
  `resources.pak` (the 1x1/2x2 tracking images, the `noop.js` family, the
  click-to-load page) are loaded into the engine as redirect resources, so a
  request that a `$redirect=` rule matches is answered with the stub's bytes
  under the original URL instead of failing. The payloads are not duplicated in
  the Paani tree: `paani_redirect_resources.cc` only holds the grit ids and the
  alias names. adblock-rust treats `$redirect-rule=` as a redirect without a
  matching block rule, and Paani's network hook only ever sees block decisions,
  so such a rule neither redirects nor blocks.
* The blocker hooks sub-resource loaders (`kDocumentSubResource`,
  `kWorkerSubResource`); top-level navigations are not filtered.
* The compiled lists are the ones Helium already bundles: uBlock's own
  `filters`, `privacy`, `quick-fixes` and `unbreak`, plus EasyList and
  EasyPrivacy. uBlock's lists alone are not enough, since most of their network
  rules are limited to specific sites or rely on a redirect. Paani adds no list
  subscription UI and downloads nothing.
* EasyList and EasyPrivacy carry their own licence notice in the header of each
  file, pointing at `https://easylist.to/pages/licence.html`, which states
  GNU GPL v3 and Creative Commons Attribution-ShareAlike 3.0. Both fit a
  GPL-3.0 fork as long as the notice stays in the file, which it does: Paani
  ships the lists unmodified.
* Vivaldi-style tab tiling, workspaces, side panels, and mail/RSS are not
  implemented. Paani's "features like Vivaldi" is limited to a customisable
  feel, a translucent frame, and a built-in blocker.
