"""Records the Paani shield button's toolbar wiring as a quilt patch.

`paani_shield_button.{h,cc}` are staged sources; this patch is only the call
sites that put the button in the toolbar and refresh it per tab.

The originals are recovered by reversing the replacements rather than by
copying the files aside, so the diff always contains exactly these hunks and
nothing another patch in the series already contributed.
"""

import difflib
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
SOURCE = ROOT / 'build' / 'src'
PATCH = ROOT / 'patches' / 'paani' / 'windows' / 'paani-shield-button.patch'

BUILD = 'chrome/browser/ui/views/toolbar/BUILD.gn'
HEADER = 'chrome/browser/ui/views/toolbar/toolbar_view.h'
SOURCE_FILE = 'chrome/browser/ui/views/toolbar/toolbar_view.cc'
VECTOR_ICONS_BUILD = 'chrome/app/vector_icons/BUILD.gn'

EDITS = [
    {
        'path': HEADER,
        'replacements': [
            (
                'class TabStripRegionView;\n'
                '\n'
                'namespace views {\n',
                'class TabStripRegionView;\n'
                '\n'
                'namespace paani {\n'
                'class PaaniShieldButton;\n'
                '}  // namespace paani\n'
                '\n'
                'namespace views {\n',
            ),
            (
                '  raw_ptr<MediaToolbarButton> media_button_ = nullptr;\n',
                '  raw_ptr<MediaToolbarButton> media_button_ = nullptr;\n'
                '  raw_ptr<paani::PaaniShieldButton> paani_shield_button_ = nullptr;\n',
            ),
        ],
    },
    {
        'path': SOURCE_FILE,
        'replacements': [
            (
                '#include "chrome/browser/ui/views/toolbar/overflow_menu.h"\n',
                '#include "chrome/browser/ui/views/toolbar/overflow_menu.h"\n'
                '#include "chrome/browser/ui/views/toolbar/paani_shield_button.h"\n',
            ),
            (
                '  if (features::IsWebUIMediaButtonEnabled()) {\n'
                '    media_button_ = toolbar_webview_->GetMediaToolbarButton();\n'
                '  } else if (media_button) {\n'
                '    media_button_ = AddChildView(std::move(media_button));\n'
                '  }\n',
                '  if (features::IsWebUIMediaButtonEnabled()) {\n'
                '    media_button_ = toolbar_webview_->GetMediaToolbarButton();\n'
                '  } else if (media_button) {\n'
                '    media_button_ = AddChildView(std::move(media_button));\n'
                '  }\n'
                '\n'
                '  // Paani\'s built in blocker has no extension popup to live in, so the\n'
                '  // per tab count and the per site allowlist are on the toolbar itself.\n'
                '  paani_shield_button_ =\n'
                '      AddChildView(std::make_unique<paani::PaaniShieldButton>(browser_));\n',
            ),
            (
                'void ToolbarView::Update(WebContents* tab) {\n'
                '  if (location_bar_) {\n'
                '    location_bar_->Update(tab);\n'
                '  }\n',
                'void ToolbarView::Update(WebContents* tab) {\n'
                '  if (location_bar_) {\n'
                '    location_bar_->Update(tab);\n'
                '  }\n'
                '\n'
                '  if (paani_shield_button_) {\n'
                '    paani_shield_button_->SetTab(tab);\n'
                '  }\n',
            ),
        ],
    },
    {
        'path': BUILD,
        'replacements': [
            (
                '    "pinned_action_toolbar_button.cc",\n',
                '    "paani_shield_button.cc",\n'
                '    "paani_shield_button.h",\n'
                '    "pinned_action_toolbar_button.cc",\n',
            ),
            (
                '    "//chrome/browser/performance_manager/public/user_tuning",\n',
                '    "//chrome/browser/paani/adblock:paani_adblock",\n'
                '    "//chrome/browser/performance_manager/public/user_tuning",\n',
            ),
            (
                '    "//ui/lottie",\n',
                '    "//ui/lottie",\n'
                '    "//ui/menus",\n',
            ),
            # The button uses these directly, so they are named here instead of
            # being picked up through another target's public_deps.
            (
                '    "//base:i18n",\n',
                '    "//base",\n'
                '    "//base:i18n",\n',
            ),
            (
                '    "//components/omnibox/browser",\n',
                '    "//components/omnibox/browser",\n'
                '    "//components/prefs",\n',
            ),
            (
                '    "//components/sessions",\n',
                '    "//components/sessions",\n'
                '    "//components/tabs:public",\n',
            ),
            (
                '    "//ui/native_theme",\n'
                '    "//ui/views/controls/webview",\n'
                '  ]\n',
                '    "//ui/native_theme",\n'
                '    "//ui/views/controls/webview",\n'
                '    "//url",\n'
                '  ]\n',
            ),
        ],
    },
    {
        'path': VECTOR_ICONS_BUILD,
        'replacements': [
            # The drop itself is staged source; only the list that makes the
            # build generate it belongs in the patch.
            (
                '    "overflow_button_touch_old.icon",\n'
                '    "paintbrush_old.icon",\n',
                '    "overflow_button_touch_old.icon",\n'
                '    "paani_drop.icon",\n'
                '    "paintbrush_old.icon",\n',
            ),
        ],
    },
]

DESCRIPTION = '''Puts the Paani blocker on the toolbar.

Paani blocks ads with its own filter engine instead of an extension, which
leaves the user no popup to open for the two things an extension would have
shown: how much was stopped on this page, and a way to stop filtering this one
page. Both belong in the toolbar, so ToolbarView creates a PaaniShieldButton in
the place where an extension icon would not sit, and ToolbarView::Update() hands
it the tab the user is looking at. The button itself, and the water drop it
wears, are staged source.
'''


def replace_once(text, needle, replacement, relative):
    if text.count(needle) != 1:
        raise SystemExit(f'{relative}: expected exactly one match for:\n{needle}')
    return text.replace(needle, replacement, 1)


def forward(text, pairs, relative):
    for old, new in pairs:
        text = replace_once(text, old, new, relative)
    return text


def backward(text, pairs, relative):
    for old, new in reversed(pairs):
        text = replace_once(text, new, old, relative)
    return text


def main():
    for edit in EDITS:
        relative = edit['path']
        path = SOURCE / relative
        current = path.read_text(encoding='utf-8')
        pairs = edit['replacements']

        # The tree is either pristine or fully patched, and an anchor can be a
        # substring of its replacement, so the state is decided by replaying
        # rather than by looking for a marker.
        try:
            original = backward(current, pairs, relative)
            if forward(original, pairs, relative) != current:
                raise SystemExit('replay mismatch')
            updated = current
        except SystemExit:
            original = current
            updated = forward(current, pairs, relative)
            path.write_text(updated, encoding='utf-8', newline='\n')
            print(f'{relative}: patched in the tree')

        diff = ''.join(difflib.unified_diff(
            original.splitlines(keepends=True),
            updated.splitlines(keepends=True),
            fromfile='a/' + relative,
            tofile='b/' + relative,
            n=3,
        ))
        if not diff:
            raise SystemExit(f'{relative}: produced no diff')
        edit['diff'] = diff

    PATCH.write_text(DESCRIPTION + ''.join(e['diff'] for e in EDITS),
                     encoding='utf-8', newline='\n')
    print(f'patch written to {PATCH}')


if __name__ == '__main__':
    main()
