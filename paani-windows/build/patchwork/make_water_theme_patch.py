"""Records the Paani water theme as a quilt patch.

The theme is three upstream edits:

* `ui/color/ref_color_mixer.cc` adds a Paani tonal palette and applies it after
  the Google baseline palette and after any palette generated from a user or
  system colour, because the browser identity is Paani's own.
* `chrome/browser/ui/color/chrome_color_mixer.cc` stops hardcoding the toolbar
  to white and dark grey.
* `chrome/browser/ui/color/win/native_chrome_color_mixer_win.cc` stops using the
  Windows accent colour for the window frame, which would otherwise leak the
  desktop theme into the header, the tab strip and the omnibox.

The originals are kept under build/patchwork/orig/water_theme so that the patch
can be regenerated from an edited tree, and re-applied to a clean unpack.
"""

import difflib
import shutil
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
SOURCE = ROOT / 'build' / 'src'
BACKUP = ROOT / 'build' / 'patchwork' / 'orig' / 'water_theme'
PATCH = ROOT / 'patches' / 'paani' / 'windows' / 'paani-water-theme.patch'

WATER_PALETTE = '''\
// The Paani water palette.
//
// Paani Browser is a personal fork whose identity is water, so these tones
// replace the Google baseline palette and any palette that was generated from a
// user or system colour.  The tonal steps keep the Material 3 spacing, so every
// contrast recipe and alpha blend downstream keeps working unchanged.
void AddPaaniWaterPalette(ColorProvider* provider,
                          ColorProviderKey::ColorMode color_mode) {
  ColorMixer& mixer = provider->AddMixer();

  // Primary: lagoon blue.
  mixer[kColorRefPrimary0] = {SkColorSetRGB(0x00, 0x00, 0x00)};
  mixer[kColorRefPrimary10] = {SkColorSetRGB(0x00, 0x1E, 0x2F)};
  mixer[kColorRefPrimary20] = {SkColorSetRGB(0x00, 0x36, 0x4D)};
  mixer[kColorRefPrimary25] = {SkColorSetRGB(0x00, 0x43, 0x5C)};
  mixer[kColorRefPrimary30] = {SkColorSetRGB(0x00, 0x4F, 0x6B)};
  mixer[kColorRefPrimary40] = {SkColorSetRGB(0x00, 0x66, 0x8A)};
  mixer[kColorRefPrimary50] = {SkColorSetRGB(0x17, 0x7C, 0xA1)};
  mixer[kColorRefPrimary60] = {SkColorSetRGB(0x3D, 0x96, 0xBB)};
  mixer[kColorRefPrimary70] = {SkColorSetRGB(0x66, 0xB2, 0xD5)};
  mixer[kColorRefPrimary80] = {SkColorSetRGB(0x8E, 0xCD, 0xF0)};
  mixer[kColorRefPrimary90] = {SkColorSetRGB(0xC9, 0xE9, 0xF7)};
  mixer[kColorRefPrimary95] = {SkColorSetRGB(0xE4, 0xF5, 0xFC)};
  mixer[kColorRefPrimary99] = {SkColorSetRGB(0xF5, 0xFB, 0xFF)};
  mixer[kColorRefPrimary100] = {SkColorSetRGB(0xFF, 0xFF, 0xFF)};

  // Secondary: sea glass.
  mixer[kColorRefSecondary0] = {SkColorSetRGB(0x00, 0x00, 0x00)};
  mixer[kColorRefSecondary10] = {SkColorSetRGB(0x08, 0x1E, 0x27)};
  mixer[kColorRefSecondary12] = {SkColorSetRGB(0x0C, 0x22, 0x2B)};
  mixer[kColorRefSecondary15] = {SkColorSetRGB(0x14, 0x29, 0x33)};
  mixer[kColorRefSecondary20] = {SkColorSetRGB(0x1F, 0x34, 0x3E)};
  mixer[kColorRefSecondary25] = {SkColorSetRGB(0x2A, 0x3F, 0x49)};
  mixer[kColorRefSecondary30] = {SkColorSetRGB(0x36, 0x4A, 0x55)};
  mixer[kColorRefSecondary35] = {SkColorSetRGB(0x42, 0x56, 0x61)};
  mixer[kColorRefSecondary40] = {SkColorSetRGB(0x4F, 0x62, 0x6D)};
  mixer[kColorRefSecondary50] = {SkColorSetRGB(0x68, 0x7B, 0x86)};
  mixer[kColorRefSecondary60] = {SkColorSetRGB(0x81, 0x95, 0xA0)};
  mixer[kColorRefSecondary70] = {SkColorSetRGB(0x9B, 0xAF, 0xB9)};
  mixer[kColorRefSecondary80] = {SkColorSetRGB(0xB6, 0xC9, 0xD4)};
  mixer[kColorRefSecondary90] = {SkColorSetRGB(0xD0, 0xE5, 0xEF)};
  mixer[kColorRefSecondary95] = {SkColorSetRGB(0xE0, 0xF2, 0xFA)};
  mixer[kColorRefSecondary99] = {SkColorSetRGB(0xF5, 0xFB, 0xFF)};
  mixer[kColorRefSecondary100] = {SkColorSetRGB(0xFF, 0xFF, 0xFF)};

  // Tertiary: reef, the teal that keeps the palette from looking flat.
  mixer[kColorRefTertiary0] = {SkColorSetRGB(0x00, 0x00, 0x00)};
  mixer[kColorRefTertiary10] = {SkColorSetRGB(0x00, 0x20, 0x1E)};
  mixer[kColorRefTertiary20] = {SkColorSetRGB(0x0B, 0x36, 0x34)};
  mixer[kColorRefTertiary30] = {SkColorSetRGB(0x1D, 0x4A, 0x48)};
  mixer[kColorRefTertiary40] = {SkColorSetRGB(0x30, 0x5D, 0x5B)};
  mixer[kColorRefTertiary50] = {SkColorSetRGB(0x46, 0x75, 0x73)};
  mixer[kColorRefTertiary60] = {SkColorSetRGB(0x5D, 0x8E, 0x8C)};
  mixer[kColorRefTertiary70] = {SkColorSetRGB(0x75, 0xA7, 0xA5)};
  mixer[kColorRefTertiary80] = {SkColorSetRGB(0x8E, 0xC1, 0xBF)};
  mixer[kColorRefTertiary90] = {SkColorSetRGB(0xA8, 0xDC, 0xDA)};
  mixer[kColorRefTertiary95] = {SkColorSetRGB(0xC3, 0xEF, 0xED)};
  mixer[kColorRefTertiary99] = {SkColorSetRGB(0xF0, 0xFB, 0xFB)};
  mixer[kColorRefTertiary100] = {SkColorSetRGB(0xFF, 0xFF, 0xFF)};

  // Neutral and neutral variant: the greys are tinted towards blue, which is
  // what makes every surface read as water rather than as plain grey.
  if (color_mode == ColorProviderKey::ColorMode::kDark) {
    mixer[kColorRefNeutral0] = {SkColorSetRGB(0x00, 0x00, 0x00)};
    mixer[kColorRefNeutral4] = {SkColorSetRGB(0x05, 0x0B, 0x0E)};
    mixer[kColorRefNeutral6] = {SkColorSetRGB(0x0A, 0x11, 0x14)};
    mixer[kColorRefNeutral8] = {SkColorSetRGB(0x0E, 0x15, 0x19)};
    mixer[kColorRefNeutral10] = {SkColorSetRGB(0x12, 0x1A, 0x1E)};
    mixer[kColorRefNeutral12] = {SkColorSetRGB(0x16, 0x1E, 0x22)};
    mixer[kColorRefNeutral15] = {SkColorSetRGB(0x1B, 0x24, 0x28)};
    mixer[kColorRefNeutral17] = {SkColorSetRGB(0x1F, 0x28, 0x2C)};
    mixer[kColorRefNeutral20] = {SkColorSetRGB(0x23, 0x2C, 0x31)};
    mixer[kColorRefNeutral22] = {SkColorSetRGB(0x27, 0x30, 0x34)};
    mixer[kColorRefNeutral24] = {SkColorSetRGB(0x2B, 0x34, 0x38)};
    mixer[kColorRefNeutral25] = {SkColorSetRGB(0x2D, 0x36, 0x3A)};
    mixer[kColorRefNeutral30] = {SkColorSetRGB(0x37, 0x40, 0x44)};
    mixer[kColorRefNeutral40] = {SkColorSetRGB(0x4B, 0x54, 0x58)};
    mixer[kColorRefNeutral50] = {SkColorSetRGB(0x63, 0x6C, 0x70)};
    mixer[kColorRefNeutral60] = {SkColorSetRGB(0x7D, 0x86, 0x8A)};
    mixer[kColorRefNeutral70] = {SkColorSetRGB(0x99, 0xA2, 0xA6)};
    mixer[kColorRefNeutral80] = {SkColorSetRGB(0xB5, 0xBE, 0xC2)};
    mixer[kColorRefNeutral87] = {SkColorSetRGB(0xC3, 0xCC, 0xD0)};
    mixer[kColorRefNeutral90] = {SkColorSetRGB(0xCD, 0xD6, 0xDA)};
    mixer[kColorRefNeutral92] = {SkColorSetRGB(0xD3, 0xDC, 0xE0)};
    mixer[kColorRefNeutral94] = {SkColorSetRGB(0xDA, 0xE3, 0xE7)};
    mixer[kColorRefNeutral95] = {SkColorSetRGB(0xDD, 0xE6, 0xEA)};
    mixer[kColorRefNeutral96] = {SkColorSetRGB(0xE4, 0xED, 0xF1)};
    mixer[kColorRefNeutral98] = {SkColorSetRGB(0xED, 0xF4, 0xF8)};
    mixer[kColorRefNeutral99] = {SkColorSetRGB(0xF1, 0xF8, 0xFB)};
    mixer[kColorRefNeutral100] = {SkColorSetRGB(0xFF, 0xFF, 0xFF)};
  } else {
    mixer[kColorRefNeutral0] = {SkColorSetRGB(0x00, 0x00, 0x00)};
    mixer[kColorRefNeutral4] = {SkColorSetRGB(0x0A, 0x10, 0x13)};
    mixer[kColorRefNeutral6] = {SkColorSetRGB(0x0F, 0x15, 0x18)};
    mixer[kColorRefNeutral8] = {SkColorSetRGB(0x13, 0x19, 0x1C)};
    mixer[kColorRefNeutral10] = {SkColorSetRGB(0x17, 0x1D, 0x20)};
    mixer[kColorRefNeutral12] = {SkColorSetRGB(0x1B, 0x21, 0x24)};
    mixer[kColorRefNeutral15] = {SkColorSetRGB(0x21, 0x27, 0x2A)};
    mixer[kColorRefNeutral17] = {SkColorSetRGB(0x25, 0x2B, 0x2E)};
    mixer[kColorRefNeutral20] = {SkColorSetRGB(0x2B, 0x31, 0x34)};
    mixer[kColorRefNeutral22] = {SkColorSetRGB(0x2F, 0x35, 0x38)};
    mixer[kColorRefNeutral24] = {SkColorSetRGB(0x33, 0x39, 0x3C)};
    mixer[kColorRefNeutral25] = {SkColorSetRGB(0x35, 0x3B, 0x3E)};
    mixer[kColorRefNeutral30] = {SkColorSetRGB(0x3F, 0x45, 0x48)};
    mixer[kColorRefNeutral40] = {SkColorSetRGB(0x52, 0x58, 0x5B)};
    mixer[kColorRefNeutral50] = {SkColorSetRGB(0x6A, 0x70, 0x73)};
    mixer[kColorRefNeutral60] = {SkColorSetRGB(0x84, 0x8A, 0x8D)};
    mixer[kColorRefNeutral70] = {SkColorSetRGB(0x9F, 0xA5, 0xA8)};
    mixer[kColorRefNeutral80] = {SkColorSetRGB(0xBB, 0xC1, 0xC4)};
    mixer[kColorRefNeutral87] = {SkColorSetRGB(0xC9, 0xCF, 0xD2)};
    mixer[kColorRefNeutral90] = {SkColorSetRGB(0xD2, 0xD8, 0xDB)};
    mixer[kColorRefNeutral92] = {SkColorSetRGB(0xD7, 0xDD, 0xE0)};
    mixer[kColorRefNeutral94] = {SkColorSetRGB(0xDD, 0xE3, 0xE6)};
    mixer[kColorRefNeutral95] = {SkColorSetRGB(0xE0, 0xE6, 0xE9)};
    mixer[kColorRefNeutral96] = {SkColorSetRGB(0xE6, 0xEC, 0xEF)};
    mixer[kColorRefNeutral98] = {SkColorSetRGB(0xED, 0xF3, 0xF6)};
    mixer[kColorRefNeutral99] = {SkColorSetRGB(0xF1, 0xF8, 0xFB)};
    mixer[kColorRefNeutral100] = {SkColorSetRGB(0xFF, 0xFF, 0xFF)};
  }

  mixer[kColorRefNeutralVariant0] = {SkColorSetRGB(0x00, 0x00, 0x00)};
  mixer[kColorRefNeutralVariant10] = {SkColorSetRGB(0x08, 0x1E, 0x27)};
  mixer[kColorRefNeutralVariant15] = {SkColorSetRGB(0x14, 0x29, 0x33)};
  mixer[kColorRefNeutralVariant20] = {SkColorSetRGB(0x1F, 0x34, 0x3E)};
  mixer[kColorRefNeutralVariant30] = {SkColorSetRGB(0x36, 0x4A, 0x55)};
  mixer[kColorRefNeutralVariant40] = {SkColorSetRGB(0x4F, 0x62, 0x6D)};
  mixer[kColorRefNeutralVariant50] = {SkColorSetRGB(0x68, 0x7B, 0x86)};
  mixer[kColorRefNeutralVariant60] = {SkColorSetRGB(0x81, 0x95, 0xA0)};
  mixer[kColorRefNeutralVariant70] = {SkColorSetRGB(0x9B, 0xAF, 0xB9)};
  mixer[kColorRefNeutralVariant80] = {SkColorSetRGB(0xB6, 0xC9, 0xD4)};
  mixer[kColorRefNeutralVariant90] = {SkColorSetRGB(0xD0, 0xE5, 0xEF)};
  mixer[kColorRefNeutralVariant95] = {SkColorSetRGB(0xE0, 0xF2, 0xFA)};
  mixer[kColorRefNeutralVariant99] = {SkColorSetRGB(0xF5, 0xFB, 0xFF)};
  mixer[kColorRefNeutralVariant100] = {SkColorSetRGB(0xFF, 0xFF, 0xFF)};
}

'''

EDITS = [
    {
        'path': 'ui/color/ref_color_mixer.cc',
        'marker': 'AddPaaniWaterPalette',
        'replacements': [
            (
                'void AddRefColorMixer(ColorProvider* provider, '
                'const ColorProviderKey& key) {',
                WATER_PALETTE +
                'void AddRefColorMixer(ColorProvider* provider, '
                'const ColorProviderKey& key) {',
            ),
            (
                '    AddGeneratedPalette(provider, user_color, variant);\n'
                '  }\n'
                '}',
                '    AddGeneratedPalette(provider, user_color, variant);\n'
                '  }\n'
                '\n'
                '  // Paani: the water palette is applied last so that it wins over the\n'
                '  // Google baseline palette and over a palette generated from a user or\n'
                '  // system colour.  Grayscale is an accessibility mode and stays alone.\n'
                '  if (key.user_color_source !=\n'
                '      ColorProviderKey::UserColorSource::kGrayscale) {\n'
                '    AddPaaniWaterPalette(provider, key.color_mode);\n'
                '  }\n'
                '}',
            ),
        ],
    },
    {
        'path': 'chrome/browser/ui/color/chrome_color_mixer.cc',
        'marker': 'Paani: the toolbar is the water surface',
        'replacements': [
            (
                '  mixer[kColorToolbar] = {dark_mode ? SkColorSetRGB(0x35, 0x36, 0x3A)\n'
                '                                    : SK_ColorWHITE};',
                '  // Paani: the toolbar is the water surface. Upstream hardcodes it to\n'
                '  // white and dark grey, which is the largest single surface of the\n'
                '  // browser and would otherwise stay out of the theme.\n'
                '  mixer[kColorToolbar] = {dark_mode ? SkColorSetRGB(0x12, 0x1A, 0x1E)\n'
                '                                    : SkColorSetRGB(0xE9, 0xF3, 0xF7)};',
            ),
        ],
    },
    {
        'path': 'chrome/browser/ui/color/win/native_chrome_color_mixer_win.cc',
        'marker': 'Paani: the window frame belongs to the water theme',
        'replacements': [
            (
                'FrameTransforms GetSystemFrameTransforms(const ui::ColorProviderKey& key) {\n'
                '  FrameTransforms frame_transforms;\n'
                '  if (const auto* const accent_color_observer = ui::AccentColorObserver::Get();\n'
                '      accent_color_observer->ShouldUseAccentColorForWindowFrame()) {\n'
                '    if (const std::optional<SkColor> dwm_frame_color =\n'
                '            accent_color_observer->accent_color()) {\n'
                '      frame_transforms.active = {dwm_frame_color.value()};\n'
                '      const std::optional<SkColor> dwm_inactive_frame_color =\n'
                '          accent_color_observer->accent_color_inactive();\n'
                '      frame_transforms.inactive =\n'
                '          dwm_inactive_frame_color.has_value()\n'
                '              ? ui::ColorTransform(dwm_inactive_frame_color.value())\n'
                '              : ui::HSLShift(\n'
                '                    {dwm_frame_color.value()},\n'
                '                    GetTint(ThemeProperties::TINT_FRAME_INACTIVE, key));\n'
                '    }\n'
                '  }\n'
                '  return frame_transforms;\n'
                '}',
                'FrameTransforms GetSystemFrameTransforms(const ui::ColorProviderKey& key) {\n'
                '  // Paani: upstream tints the window frame with the Windows accent colour,\n'
                '  // which leaks the desktop theme into the frame, the header, the tab strip\n'
                '  // and the omnibox.  The frame is part of the water identity instead, and\n'
                '  // the inactive shade keeps upstream\'s relationship to the active one.\n'
                '  const bool dark_mode =\n'
                '      key.color_mode == ui::ColorProviderKey::ColorMode::kDark;\n'
                '  const SkColor active_frame =\n'
                '      dark_mode ? SkColorSetRGB(0x0F, 0x17, 0x1B)\n'
                '                : SkColorSetRGB(0xDC, 0xEC, 0xF3);\n'
                '\n'
                '  FrameTransforms frame_transforms;\n'
                '  frame_transforms.active = {active_frame};\n'
                '  frame_transforms.inactive = ui::HSLShift(\n'
                '      {active_frame}, GetTint(ThemeProperties::TINT_FRAME_INACTIVE, key));\n'
                '  return frame_transforms;\n'
                '}',
            ),
        ],
    },
]

DESCRIPTION = '''Themes the browser chrome with the Paani water palette.

The palette is injected in ui/color/ref_color_mixer.cc, which is the single
upstream of every GM3 brand token.  Replacing it there recolours the toolbar,
the tab strip, the omnibox, the buttons, and every chrome:// page, because the
WebUI custom properties are generated from the same ColorIds.

The toolbar no longer hardcodes white and dark grey, and on Windows the frame
stops following the desktop accent colour so that the identity stays Paani's own.
'''


def main():
    BACKUP.mkdir(parents=True, exist_ok=True)
    chunks = [DESCRIPTION]

    for edit in EDITS:
        relative = edit['path']
        path = SOURCE / relative
        current = path.read_text(encoding='utf-8')

        if edit['marker'] in current:
            original = None
            backup = BACKUP / (relative.replace('/', '_') + '.orig')
            if backup.exists():
                original = backup.read_text(encoding='utf-8')
            if original is None:
                raise SystemExit(
                    f'{relative}: already themed but no pristine copy in {backup}')
        else:
            original = current
            shutil.copyfile(path, BACKUP / (relative.replace('/', '_') + '.orig'))
            updated = current
            for old, new in edit['replacements']:
                if old not in updated:
                    raise SystemExit(f'{relative}: anchor not found:\n{old}')
                updated = updated.replace(old, new, 1)
            path.write_text(updated, encoding='utf-8', newline='\n')
            current = updated

        diff = ''.join(difflib.unified_diff(
            original.splitlines(keepends=True),
            current.splitlines(keepends=True),
            fromfile='a/' + relative,
            tofile='b/' + relative,
            n=3,
        ))
        if not diff:
            raise SystemExit(f'{relative}: produced no diff')
        chunks.append(diff)

    PATCH.write_text(''.join(chunks), encoding='utf-8', newline='\n')
    print(f'patch written to {PATCH}')


if __name__ == '__main__':
    main()
