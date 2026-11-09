"""Records the chrome://paani wiring as a quilt patch.

The upstream files below are edited in place in build/src; this reverses
each edit to recover the pristine text, diffs the two and writes
patches/paani/windows/paani-webui-page.patch, so the same edits can be replayed
on a clean unpack.
"""

import difflib
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
SOURCE = ROOT / 'build' / 'src'
BACKUP = ROOT / 'build' / 'patchwork' / 'orig' / 'webui'
PATCH = ROOT / 'patches' / 'paani' / 'windows' / 'paani-webui-page.patch'

# repo relative path -> list of blocks that the Paani layer adds.
EDITS = {
    'chrome/common/webui_url_constants.h': [
        'inline constexpr char kChromeUIPaaniHost[] = "paani";\n'
        'inline constexpr char kChromeUIPaaniURL[] = "chrome://paani/";\n',
    ],
    'chrome/browser/ui/webui/chrome_web_ui_configs.cc': [
        '#include "chrome/browser/ui/webui/paani/paani_ui.h"\n',
        '  map.AddWebUIConfig(std::make_unique<PaaniUIConfig>());\n',
    ],
    'chrome/browser/ui/webui/BUILD.gn': [
        '      "//chrome/browser/ui/webui/paani",\n',
    ],
    'chrome/browser/resources/BUILD.gn': [
        '      "paani:resources",\n',
    ],
    # grit builds the page into chrome/paani_resources.pak, but resources.pak
    # is assembled from an explicit list of module paks; without this entry the
    # WebUI resource ids compile into the binary but are missing at runtime and
    # chrome://paani renders an empty document.
    'chrome/chrome_paks.gni': [
        '        "$root_gen_dir/chrome/paani_resources.pak",\n',
    ],
    'chrome/browser/profiles/chrome_browser_main_extra_parts_profiles.cc': [
        '#include "chrome/browser/paani/adblock/paani_adblock_service.h"\n',
        '  paani::PaaniAdblockServiceFactory::GetInstance();\n',
    ],
    # A MojoWebUIController only receives interface requests for the interfaces
    # listed in this registry, see the instructions at the top of
    # ui/webui/mojo_web_ui_controller.h.  Without the entry the page loads but
    # the renderer is killed with "No binder found for interface
    # paani.mojom.PageHandlerFactory" as soon as it asks for the ad blocker
    # state, so the counter and the allowlist stay dead.
    'chrome/browser/chrome_browser_interface_binders_webui_parts_desktop.cc': [
        '#include "chrome/browser/ui/webui/paani/paani_ui.h"\n',
        '''  // chrome://paani talks to the built in ad blocker through this factory. The
  // page can render without it, but every call from it then fails and the
  // browser kills the renderer with "No binder found for interface
  // paani.mojom.PageHandlerFactory".
  registry.ForWebUI<PaaniUI>()
      .Add<paani::mojom::PageHandlerFactory>();

''',
    ],
    'chrome/browser/profiles/BUILD.gn': [
        '    "//chrome/browser/paani/adblock:paani_adblock",\n',
    ],
    'third_party/lit/v3_0/BUILD.gn': [
        '    "//chrome/browser/resources/paani:build_ts",\n',
    ],
    'tools/gritsettings/resource_ids.spec': [
        '  "<(SHARED_INTERMEDIATE_DIR)/chrome/browser/resources/paani/'
        'resources.grd": {\n'
        '    "META": {"sizes": {"includes": [10]}},\n'
        '    "includes": [5400],\n'
        '  },\n',
    ],
}

DESCRIPTION = '''Adds the chrome://paani page and registers the ad blocker service.

The page shows the number of requests the built in ad blocker stopped and lets
the user allow a site.  It is a plain WebUI: a mojom handler on the browser
side and a Lit element on the page side.

PaaniAdblockServiceFactory is instantiated from
EnsureBrowserContextKeyedServiceFactoriesBuilt() so that the factory is
registered, and its preferences are registered, before a profile is created.

grit gives every .grd its own block of resource ids, taken from the table in
tools/gritsettings/resource_ids.spec; without a paani entry the resources_grit
action fails with "Please update default_resource_ids and add a first id".

paani::mojom::PageHandlerFactory is added to the WebUI interface binder
registry.  A MojoWebUIController that is not listed there never receives the
renderer's bind request, and the renderer is terminated for a bad message as
soon as chrome://paani asks for the ad blocker state.
'''


def main():
    BACKUP.mkdir(parents=True, exist_ok=True)
    chunks = [DESCRIPTION]
    for relative, blocks in EDITS.items():
        path = SOURCE / relative
        current = path.read_text(encoding='utf-8')
        original = current
        for block in blocks:
            if block not in original:
                raise SystemExit(f'{relative}: {block!r} is not in the tree')
            original = original.replace(block, '', 1)

        backup = BACKUP / (relative.replace('/', '_') + '.orig')
        backup.write_text(original, encoding='utf-8', newline='\n')

        diff = difflib.unified_diff(
            original.splitlines(keepends=True),
            current.splitlines(keepends=True),
            fromfile='a/' + relative,
            tofile='b/' + relative,
            n=3,
        )
        chunks.append(''.join(diff))

    PATCH.write_text(''.join(chunks), encoding='utf-8', newline='\n')
    print(f'patch written to {PATCH}')


if __name__ == '__main__':
    main()
