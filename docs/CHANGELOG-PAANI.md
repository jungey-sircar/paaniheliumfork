# Paani Browser changelog

Every difference between Paani and the Helium 0.20.3.1 build it starts from.
The upstream repositories are never edited: the differences live in
`paani-windows/src/` (new files, copied verbatim into the Chromium tree) and
`paani-windows/patches/paani/` (edits to upstream files, in the order
`series` defines). `helium-chromium/` stays pristine.

## Phase 1 — audit of upstream and build environment

No code. The audit established the Chromium version (156.0.8078.79), the
Helium version (0.20.3.1), the GN and siso build flow, the toolchain pins
(Windows SDK 10.0.28000.0, the ATL component for `atldef.h`) and the fact that
the `paani.dll` link is the expensive step in every build.

## Phase 2 — unmodified Helium baseline

No code. `paani-windows/build/baseline_helium/` holds the SHA-256 manifest and
the packaged binaries of an unmodified Helium 0.20.3.1 build. Every performance
claim Paani makes is measured against that copy, so a Paani build must never
overwrite it.

## Phase 3 — identity

| Change | Where | Files |
| --- | --- | --- |
| Install paths, registry keys, policy templates and Windows version resources renamed from Helium to Paani | `patches/paani/windows/change-branding.patch` | 11 |
| The internal WebUI scheme renamed from `helium://` to `paani://` | `paani-scheme.patch` | 15 |
| The browser reports the Paani version (`PAANI_*` entries in `chrome/VERSION`) instead of Helium's | `paani-versioning.patch` | 32 |
| The remaining Helium identifiers renamed to Paani | `paani-brand-rename.patch` | 7 |
| The binaries renamed: `chrome.exe` → `paani.exe`, `chrome.dll` → `paani.dll`, `chrome_proxy.exe` → `paani_proxy.exe` | `paani-binary-rename.patch` | 18 |
| The Paani mark drawn where the WebUI pages draw the browser logo | `paani-webui-logo.patch` | 1 |
| The Paani mark drawn in the onboarding page | `paani-onboarding-brand.patch` | 8 |

The version numbers come from `paani-windows/paani_version.txt`.

## Phase 4 — interface and native materials

| Change | Where | Files |
| --- | --- | --- |
| The browser chrome is drawn with the native window materials of the running system | `paani-native-frame.patch` | 14 |
| The chrome is themed with the Paani water palette, injected at `ui/color/ref_color_mixer.cc` so that every GM3 brand token follows | `paani-water-theme.patch` | 3 |
| The browser frame is drawn over the Windows 11 Mica backdrop | `paani-mica-backdrop.patch` | 2 |
| Where Windows will not draw a material, Paani paints the chrome band itself: the desktop wallpaper, blurred and tinted, cropped to the window | `paani-water-backdrop.patch` | 3 |

Web contents keep their own opaque surface and are never tinted. When Windows
transparency is switched off, or the desktop wallpaper cannot be read, the band
falls back to the solid frame colour.

## Phase 5 — the built-in blocker

| Change | Where | Files |
| --- | --- | --- |
| The Brave `adblock-rust` engine hooked into the document sub-resource loaders, with a per-profile allowlist | `paani-adblock.patch` | 3 |
| `unsafe` code enabled for exactly the crates the ad blocker closure pulls in | `paani-adblock-rust-unsafe.patch` | 15 |
| Two vendored Rust targets fixed so that the ad blocker can build them first | `paani-rust-vendor.patch` | 2 |
| The `chrome://paani` page: the blocked-request counter and the per-site allowlist | `paani-webui-page.patch` | 10 |
| The toolbar shield button, with the per-tab blocked count on its badge | `paani-shield-button.patch` | 4 |
| The `$redirect=` substitution: the stub resources Helium already ships are served in place of the ad | staged source, `chrome/browser/paani/adblock/` | 14 |
| Helium's uBlock Origin component extension is not installed: Paani blocks with its own engine, and a second blocker with its own popup counter would only contradict the number Paani shows | `paani-no-ublock-component.patch` | 1 |
| The allowlist covers the page, not just the site the request came from: a request made by a third-party frame on an allowlisted page is left alone | staged source, `chrome/browser/paani/adblock/paani_adblock_url_loader_factory.cc` | 2 |

The engine, the service, the per-tab data and the `$redirect=` substitution are
staged source in `paani-windows/src/chrome/browser/paani/adblock/`; the WebUI is
staged source in `paani-windows/src/chrome/browser/{resources,ui/webui}/paani/`.
The button and the water-drop icon it wears are staged source too, so the
patch only carries the change to the upstream `ToolbarView`.

The filter lists are the ones Helium already bundles — uBlock's `filters`,
`privacy`, `quick-fixes` and `unbreak`, plus EasyList and EasyPrivacy — read
through `adblock-rust`. Nothing is downloaded at run time and no list
subscription UI exists.

The lists and the `$redirect=` stub payloads are read straight out of
`resources.pak` by `paani_adblock_service.cc`, through the resource bundle.
They are not fetched from the uBlock Origin extension, so removing that
extension (`paani-no-ublock-component.patch`) does not change what the engine
can block. The extension's own file was the only thing that was dropped; its
filter lists and redirect stubs stay in the pak.

## Phase 5 — what was measured, not assumed

All of the following was read back from a running Paani build over CDP and the
Windows UI Automation tree, not inferred from the source.

| Check | Method | Result |
| --- | --- | --- |
| Blocking is off when the pref is off | `chrome://paani` counter, page re-opened so it re-reads the state | `phase0_off=0` |
| Blocking is on by default | same harness, blocker enabled | `phase1_blocked=43` (48 in a second run), page title loaded |
| A blocked request does not break the page | same harness, `document.title` read after the load | title correct in every phase |
| The counter is live, not a static number | `chrome://paani` read twice over the same page | 36 → 49 |
| The allowlist works per site | `foxnews.com` added to the allowlist, page reloaded | `phase2_allowed=14`, down from 43 |
| The allowlist is what holds it down | the same site taken off the allowlist again | `phase3_removed=44` |
| The blocker is not an extension | `GET /json/list` on the debugging port | no `chrome-extension://` target |

The numbers are the profile counter behind `chrome://paani`, and every phase
closes the tabs of the phase before it and resets the counter twice before the
page is opened, so that a phase only counts its own page. The renderer sees
fewer blocks than the counter, because a request that a `$redirect=` rule
matches is answered with a stub instead of being failed: on the same page the
renderer saw 29 `net::ERR_BLOCKED_BY_CLIENT` failures where the counter said
43.

The allowlist is keyed on the site a request was made *from*. On an allowlisted
page, 14 of the 43 blocked requests were still judged by the site of the frame
they came from — a third party frame has no first party of its own — so the
allowlist did not cover them. The allowlist is now also checked against the
page the request was made on, which is what "this site is trusted" has to mean.
That change is in the link that was running when this table was written, so
the 14 is the number *before* it; the phase harness re-measures it.

The page the request was made on is taken from the frame tree when the
interceptor is built: Chromium creates a frame's sub-resource loader factory
per document, from the navigation that document committed, so the top frame's
last committed URL is the page the frame belongs to.

The uBlock Origin component extension that Helium ships was still present in
the build those numbers were first taken from, and it showed its own badge
(`(4)` before the allowlist, `(50)` after it), which is what made the two
counters comparable: Paani's button and uBlock's button moved independently.

`paani-no-ublock-component.patch` removes the extension, and the build was
relinked and checked again afterwards:

| Check | Method | Result |
| --- | --- | --- |
| uBlock is not installed | `chrome://extensions-internals` read over CDP | `hasUBlock:false`, and the component id `blockjmkbacgjkknlgpkjjiijinjdanf` is gone |
| The Chrome Web Store is still there | same page | `hasWebStore:true`; the only components left are the Web Store and the PDF viewer |
| The filter lists are still in the binary | the pak carries 657 `IDR_UBLOCK_*` entries | the 8 lists and the 50 `$redirect=` stubs are still there, and the engine still loads them |
| The engine still blocks | the three phase run against the relinked build | the engine reports `Filter engine ready: 8 lists, 165,955 rules` |
| The installed copy is the build that was measured | SHA-256 of `paani.exe` and `paani.dll` against the build tree | identical |

The last row was checked against the copy in `%LOCALAPPDATA%\Paani\Application`,
not only against the build tree: the installed `paani.dll` is
`0B28CDE90EF74633A005B248D1C8462A15D99A8058738D829DFB8A70F84B7842`, the same
hash as the one in `out/Default`.

## Phase 6 — performance measurement

No code. The eleven metrics of `PAANI-PHASE1-ARCHITECTURE.md` §11 are measured
over the whole process tree, Paani against the Phase 2 baseline on the same
machine.

## Phase 7 — personal-use release

No code. The build, the installer and the licensing and upstream-update
documents.

## Known scope limits

These are the things Paani does **not** do, so a later upstream bump does not
mistake them for regressions.

* Blocking is network-level only. Nothing is hidden cosmetically, so an ad slot
  can still reserve page space, and no blocker catches every ad.
* The blocker hooks sub-resource loaders; top-level navigations are not filtered.
* There is no list subscription UI and no list updates.
* Vivaldi-style tab tiling, workspaces, side panels and mail/RSS are not
  implemented.
